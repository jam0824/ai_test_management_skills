package jp.sample.retirementsimulator

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.random.Random

/** 手取りとシミュレーションの計算が仕様どおりかを確かめる */
class SimulatorTest {

    /** 決めた順に値を返す乱数(イベントの発生を固定するため) */
    private class FixedRandom(vararg values: Double) : Random() {
        private val queue = ArrayDeque(values.toList())
        override fun nextBits(bitCount: Int): Int = error("使わない")
        override fun nextDouble(): Double = queue.removeFirstOrNull() ?: 0.99
    }

    /** 何も起きない最小の条件。テストごとに必要なところだけ変える */
    private fun baseOptions() = SimulationOptions(
        startAge = 100.0, retirementAge = 100.0, pensionStartAge = 100.0, gapIncome = 0.0,
        salary = 0.0, salaryChanges = emptyList(), monthlyPension = 0.0,
        initialCash = 0.0, initialInv = 0.0,
        expenseCurrent = 0.0, expenseGap = 0.0, expenseRetired = 0.0,
        investRate = 0.0, annualInterest = 0.0,
        eventProb = 0.0, eventTypes = emptyList(),
    )

    // ---- 手取り計算 ----

    @Test
    fun `年収0円の手取りは0円`() {
        assertEquals(0.0, Simulator.calculateNetMonthly(0.0), 0.0)
    }

    @Test
    fun `年収120万円の手取りは月79100円`() {
        // 社会保険料168000、課税所得552000、所得税27600、住民税55200
        assertEquals(79100.0, Simulator.calculateNetMonthly(1_200_000.0), 1e-9)
    }

    @Test
    fun `年収500万円では所得税の3つの税率をまたいで計算する`() {
        // 課税所得3820000 → 195万×5% + 135万×10% + 52万×20% = 336500
        assertEquals(3_581_500.0 / 12, Simulator.calculateNetMonthly(5_000_000.0), 1e-9)
    }

    // ---- 期間ごとの収入と生活費 ----

    @Test
    fun `退職後から年金開始までは退職後収入とその期間の生活費を使う`() {
        // Web版の runTests と同じ条件
        val lines = Simulator.simulateRetirement(
            baseOptions().copy(
                startAge = 65.0, retirementAge = 65.0, pensionStartAge = 67.0, gapIncome = 5000.0,
                expenseCurrent = 100.0, expenseGap = 200.0, expenseRetired = 300.0,
            )
        )
        assertEquals("-- 65歳1月 --", lines[0])
        assertEquals("  退職後収入: ¥5,000", lines[1])
        assertEquals("  生活費: ¥200", lines[2])
        assertEquals("  現金: ¥4,800 投資: ¥0 総資産: ¥4,800", lines[3])
    }

    @Test
    fun `年金開始後は年金と老後生活費を使う`() {
        val lines = Simulator.simulateRetirement(
            baseOptions().copy(monthlyPension = 145000.0, expenseRetired = 228000.0)
        )
        assertEquals("  年金: ¥145,000", lines[1])
        assertEquals("  生活費: ¥228,000", lines[2])
    }

    @Test
    fun `現役中は手取りの一部を投資に回し残りを現金にする`() {
        val lines = Simulator.simulateRetirement(
            baseOptions().copy(startAge = 99.0, retirementAge = 100.0, salary = 1_200_000.0, investRate = 0.2)
        )
        assertEquals("  給与: ¥79,100 (投資: ¥15,820)", lines[1])
        assertEquals("  現金: ¥63,280 投資: ¥15,820 総資産: ¥79,100", lines[3])
    }

    @Test
    fun `開始年齢から100歳12月まで毎月の行を出す`() {
        val lines = Simulator.simulateRetirement(baseOptions().copy(startAge = 99.0))
        // 2年×12か月×4行 + 100歳1月の利息2行
        assertEquals(2 * 12 * 4 + 2, lines.size)
        assertEquals("-- 100歳12月 --", lines[lines.size - 4])
    }

    @Test
    fun `開始年齢が100歳を超えると何も出さない`() {
        assertTrue(Simulator.simulateRetirement(baseOptions().copy(startAge = 101.0)).isEmpty())
    }

    // ---- 給与変更 ----

    @Test
    fun `給与変更の入力は年齢と年収が正のものだけを年齢の降順に並べる`() {
        val changes = Simulator.buildSalaryChanges(
            listOf("35" to "4000000", "40歳" to "7000000", "" to "5000000", "45" to "0")
        )
        assertEquals(listOf(SalaryChange(40.0, 7_000_000.0), SalaryChange(35.0, 4_000_000.0)), changes)
    }

    @Test
    fun `給与変更の年齢に達したら変更後の年収で計算し年収も表示する`() {
        val lines = Simulator.simulateRetirement(
            baseOptions().copy(
                startAge = 99.0, retirementAge = 101.0, salary = 0.0,
                salaryChanges = listOf(SalaryChange(100.0, 1_200_000.0)),
            )
        )
        assertEquals("  給与: ¥0 (投資: ¥0)", lines[1])
        val age100Jan = lines.indexOf("-- 100歳1月 --")
        assertEquals("  給与: ¥79,100 (投資: ¥0) [年収: ¥1,200,000]", lines[age100Jan + 1])
    }

    // ---- 投資 ----

    @Test
    fun `2年目以降の1月に投資残高へ年利をかける`() {
        val lines = Simulator.simulateRetirement(
            baseOptions().copy(startAge = 99.0, initialInv = 1000.0, annualInterest = 0.04)
        )
        val idx = lines.indexOf("== 100歳 1月: 投資利息 ==")
        assertEquals("  投資: ¥1,000 → ¥1,040", lines[idx + 1])
        assertEquals("-- 100歳1月 --", lines[idx + 2])
    }

    @Test
    fun `現金が足りないと投資から補填し補填額の20パーセントを税金として投資から引く`() {
        val lines = Simulator.simulateRetirement(
            baseOptions().copy(initialInv = 1000.0, expenseRetired = 100.0)
        )
        assertEquals("  🔄 投資から補填: ¥100 (税金: ¥20)", lines[3])
        assertEquals("  現金: ¥0 投資: ¥880 総資産: ¥880", lines[4])
    }

    // ---- 突発的なイベント ----

    @Test
    fun `イベントが起きると費用を現金から引いて行に出す`() {
        val events = listOf(LifeEvent("入院", 200000.0), LifeEvent("車検", 80000.0))
        // 1つ目: 発生判定(0.0 < 0.5で発生)、2つ目: 種類の選択(0.6 → 2番目)
        val lines = Simulator.simulateRetirement(
            baseOptions().copy(initialCash = 100000.0, eventProb = 0.5, eventTypes = events),
            FixedRandom(0.0, 0.6),
        )
        assertEquals("  ▶ 車検: ¥80,000", lines[3])
        assertEquals("  現金: ¥20,000 投資: ¥0 総資産: ¥20,000", lines[4])
    }

    @Test
    fun `画面の既定のイベントはWeb版と同じ8種類`() {
        assertEquals(
            listOf("入院", "歯科治療", "薬の購入", "家電故障", "車検", "冠婚葬祭", "健康診断", "引越し"),
            Simulator.DEFAULT_EVENT_TYPES.map { it.name },
        )
    }
}
