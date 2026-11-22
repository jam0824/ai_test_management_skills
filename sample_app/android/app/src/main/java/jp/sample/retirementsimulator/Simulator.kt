package jp.sample.retirementsimulator

import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min
import kotlin.random.Random

/** 給与変更(この年齢から、この年収になる) */
data class SalaryChange(val age: Double, val salary: Double)

/** 突発的な支出 */
data class LifeEvent(val name: String, val cost: Double)

/** シミュレーションの条件。率はすべて小数(20% なら 0.2) */
data class SimulationOptions(
    val startAge: Double,
    val retirementAge: Double,
    val pensionStartAge: Double,
    val gapIncome: Double,
    val salary: Double,
    /** 年齢の降順に並んでいること(buildSalaryChanges で作る) */
    val salaryChanges: List<SalaryChange>,
    val monthlyPension: Double,
    val initialCash: Double,
    val initialInv: Double,
    val expenseCurrent: Double,
    val expenseGap: Double,
    val expenseRetired: Double,
    val investRate: Double,
    val annualInterest: Double,
    val eventProb: Double,
    val eventTypes: List<LifeEvent>,
)

/** 老後資金の計算。仕様はWeb版と同じ(sample_app/web/README.md) */
object Simulator {

    private data class Bracket(val up: Double, val rate: Double)

    private val BRACKETS = listOf(
        Bracket(1_950_000.0, 0.05), Bracket(3_300_000.0, 0.10),
        Bracket(6_950_000.0, 0.20), Bracket(9_000_000.0, 0.23),
        Bracket(18_000_000.0, 0.33), Bracket(40_000_000.0, 0.40),
        Bracket(Double.POSITIVE_INFINITY, 0.45),
    )

    val DEFAULT_EVENT_TYPES = listOf(
        LifeEvent("入院", 200_000.0), LifeEvent("歯科治療", 50_000.0), LifeEvent("薬の購入", 20_000.0),
        LifeEvent("家電故障", 100_000.0), LifeEvent("車検", 80_000.0), LifeEvent("冠婚葬祭", 120_000.0),
        LifeEvent("健康診断", 30_000.0), LifeEvent("引越し", 200_000.0),
    )

    /** 年収から月の手取りを出す(社会保険料14%、所得税は累進、住民税10%、基礎控除48万円) */
    fun calculateNetMonthly(salaryAnnual: Double): Double {
        val social = salaryAnnual * 0.14
        val taxable = max(0.0, salaryAnnual - social - 480_000)
        var tax = 0.0
        var prev = 0.0
        for (b in BRACKETS) {
            if (taxable <= prev) break
            tax += (min(b.up, taxable) - prev) * b.rate
            prev = b.up
        }
        val resident = taxable * 0.10
        return (salaryAnnual - social - tax - resident) / 12
    }

    /**
     * 画面の給与変更の入力(年齢, 年収)を条件に変える。
     * 年齢と年収がどちらも正のものだけを残し、年齢の降順に並べる。
     */
    fun buildSalaryChanges(rows: List<Pair<String, String>>): List<SalaryChange> =
        rows.mapNotNull { (ageText, salaryText) ->
            val age = JsFormat.parseFloat(ageText) ?: return@mapNotNull null
            val salary = JsFormat.parseFloat(salaryText) ?: return@mapNotNull null
            if (age > 0 && salary > 0) SalaryChange(age, salary) else null
        }.sortedByDescending { it.age }

    fun simulateRetirement(opts: SimulationOptions, random: Random = Random.Default): List<String> {
        val yen = JsFormat::toLocaleString
        val round = JsFormat::round

        fun currentSalary(age: Double): Double =
            opts.salaryChanges.firstOrNull { age >= it.age }?.salary ?: opts.salary

        var cash = opts.initialCash
        var investBal = opts.initialInv
        val lines = mutableListOf<String>()

        var age = opts.startAge
        while (age <= 100) {
            val ageText = JsFormat.toJsString(age)
            for (m in 1..12) {
                // 年初 投資残高へ利息適用
                if (m == 1 && age > opts.startAge) {
                    val before = investBal
                    investBal *= (1 + opts.annualInterest)
                    lines += "== ${ageText}歳 1月: 投資利息 =="
                    lines += "  投資: ¥${yen(before)} → ¥${yen(round(investBal))}"
                }
                // 収入判定
                val incomeText: String
                if (age < opts.retirementAge) {
                    val salary = currentSalary(age)
                    val net = calculateNetMonthly(salary)
                    val invAmt = net * opts.investRate
                    investBal += invAmt
                    cash += (net - invAmt)
                    var text = "給与: ¥${yen(round(net))} (投資: ¥${yen(round(invAmt))})"
                    if (salary != opts.salary) text += " [年収: ¥${yen(salary)}]"
                    incomeText = text
                } else if (age < opts.pensionStartAge) {
                    cash += opts.gapIncome
                    incomeText = "退職後収入: ¥${yen(opts.gapIncome)}"
                } else {
                    cash += opts.monthlyPension
                    incomeText = "年金: ¥${yen(opts.monthlyPension)}"
                }
                // 生活費差引
                val cost = when {
                    age < opts.retirementAge -> opts.expenseCurrent
                    age < opts.pensionStartAge -> opts.expenseGap
                    else -> opts.expenseRetired
                }
                cash -= cost
                // イベント
                val evtLines = mutableListOf<String>()
                if (random.nextDouble() < opts.eventProb) {
                    val e = opts.eventTypes[floor(random.nextDouble() * opts.eventTypes.size).toInt()]
                    cash -= e.cost
                    evtLines += "▶ ${e.name}: ¥${yen(e.cost)}"
                }
                // 投資補填
                if (cash < 0 && investBal > 0) {
                    val need = -cash
                    val draw = min(investBal, need)
                    val tax = draw * 0.2 // 20%の税金
                    investBal -= (draw + tax) // 補填額 + 税金を引く
                    cash += draw // 現金には補填額のみ追加
                    evtLines += "🔄 投資から補填: ¥${yen(draw)} (税金: ¥${yen(round(tax))})"
                }
                // 出力
                lines += "-- ${ageText}歳${m}月 --"
                lines += "  $incomeText"
                lines += "  生活費: ¥${yen(cost)}"
                evtLines.forEach { lines += "  $it" }
                val total = cash + investBal
                lines += "  現金: ¥${yen(round(cash))} 投資: ¥${yen(round(investBal))} 総資産: ¥${yen(round(total))}"
            }
            age += 1
        }
        return lines
    }
}
