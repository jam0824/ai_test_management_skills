package jp.sample.retirementsimulator

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel

/** 入力欄1つ分。id はWeb版の input の id と同じ */
data class InputField(val id: String, val label: String, val default: String, val decimal: Boolean = false)

/** 給与変更の入力1行分 */
data class SalaryChangeRow(val key: Long, val age: String = "", val salary: String = "")

/** 画面の状態。画面を回転しても入力と結果が残るよう ViewModel に持たせる */
class SimulatorViewModel : ViewModel() {

    companion object {
        /** 給与変更設定より上に並ぶ欄 */
        val FIELDS_BEFORE_SALARY_CHANGES = listOf(
            InputField("startAge", "シミュレーション開始年齢", "30"),
            InputField("retirementAge", "退職年齢", "65"),
            InputField("pensionStartAge", "年金開始年齢", "65"),
            InputField("gapIncome", "退職後収入(月額)", "0"),
            InputField("salary", "給与(年収)", "3000000"),
        )

        /** 給与変更設定より下に並ぶ欄 */
        val FIELDS_AFTER_SALARY_CHANGES = listOf(
            InputField("monthlyPension", "年金月額", "145000"),
            InputField("initialCash", "開始時貯金", "1000000"),
            InputField("initialInv", "開始時投資残高", "0"),
            InputField("expenseCurrent", "現役時生活費(月額)", "155600"),
            InputField("expenseGap", "退職～年金開始期間の生活費(月額)", "228000"),
            InputField("expenseRetired", "老後生活費(月額)", "228000"),
            InputField("investRate", "投資率(%)", "20"),
            InputField("interest", "利回り(年%)", "4", decimal = true),
            InputField("eventProb", "イベント発生率(月%)", "1", decimal = true),
        )
    }

    private val values = mutableStateMapOf<String, String>().apply {
        (FIELDS_BEFORE_SALARY_CHANGES + FIELDS_AFTER_SALARY_CHANGES).forEach { put(it.id, it.default) }
    }

    val salaryChanges = mutableStateListOf<SalaryChangeRow>()
    private var nextKey = 0L

    var showSalaryChanges by mutableStateOf(false)
        private set

    var output by mutableStateOf<List<String>>(emptyList())
        private set

    fun value(id: String): String = values.getValue(id)

    fun setValue(id: String, text: String) {
        values[id] = text
    }

    fun toggleSalaryChanges() {
        showSalaryChanges = !showSalaryChanges
    }

    fun addSalaryChange() {
        salaryChanges += SalaryChangeRow(nextKey++)
    }

    fun updateSalaryChange(row: SalaryChangeRow) {
        val index = salaryChanges.indexOfFirst { it.key == row.key }
        if (index >= 0) salaryChanges[index] = row
    }

    fun removeSalaryChange(key: Long) {
        salaryChanges.removeAll { it.key == key }
    }

    /** Web版の runSimulation と同じ。数として読めない欄は0として扱う */
    fun run() {
        fun get(id: String) = JsFormat.parseFloat(values.getValue(id)) ?: 0.0
        val opts = SimulationOptions(
            startAge = get("startAge"), retirementAge = get("retirementAge"),
            pensionStartAge = get("pensionStartAge"), gapIncome = get("gapIncome"),
            salary = get("salary"),
            salaryChanges = Simulator.buildSalaryChanges(salaryChanges.map { it.age to it.salary }),
            monthlyPension = get("monthlyPension"),
            initialCash = get("initialCash"), initialInv = get("initialInv"),
            expenseCurrent = get("expenseCurrent"), expenseGap = get("expenseGap"),
            expenseRetired = get("expenseRetired"),
            investRate = get("investRate") / 100, annualInterest = get("interest") / 100,
            eventProb = get("eventProb") / 100,
            eventTypes = Simulator.DEFAULT_EVENT_TYPES,
        )
        output = Simulator.simulateRetirement(opts)
    }
}
