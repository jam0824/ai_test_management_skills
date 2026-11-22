package jp.sample.retirementsimulator

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel

/**
 * 画面の部品の testTag。testTagsAsResourceId を有効にしているので、
 * UI Automator や Appium からは resource-id として見える。
 * 入力欄の tag はWeb版の input の id と同じ(startAge など)。
 */
object TestTags {
    const val SCREEN = "screen"
    const val SALARY_CHANGE_TOGGLE = "toggleSalaryChanges"
    const val SALARY_CHANGE_PANEL = "salaryChanges"
    const val SALARY_CHANGE_ADD = "addSalaryChange"
    const val SALARY_CHANGE_AGE = "salaryChangeAge"
    const val SALARY_CHANGE_SALARY = "salaryChangeSalary"
    const val SALARY_CHANGE_DELETE = "salaryChangeDelete"
    const val RUN = "runBtn"
    const val OUTPUT_LINE = "outputLine"
}

@OptIn(ExperimentalComposeUiApi::class)
@Composable
fun RetirementSimulatorScreen(vm: SimulatorViewModel = viewModel()) {
    MaterialTheme {
        Surface(
            modifier = Modifier
                .fillMaxSize()
                .semantics { testTagsAsResourceId = true },
        ) {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .safeDrawingPadding()
                    .imePadding()
                    .testTag(TestTags.SCREEN),
                contentPadding = PaddingValues(16.dp),
            ) {
                item {
                    Text("老後資金シミュレーター", fontSize = 24.sp, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(12.dp))
                    PrivacyNote()
                    Spacer(Modifier.height(12.dp))
                }
                items(SimulatorViewModel.FIELDS_BEFORE_SALARY_CHANGES, key = { it.id }) { field ->
                    NumberField(field, vm)
                }
                item {
                    OutlinedButton(
                        onClick = vm::toggleSalaryChanges,
                        modifier = Modifier
                            .padding(vertical = 8.dp)
                            .testTag(TestTags.SALARY_CHANGE_TOGGLE),
                    ) { Text("📈 給与変更設定を表示/非表示") }
                }
                if (vm.showSalaryChanges) {
                    item { SalaryChangePanel(vm) }
                }
                items(SimulatorViewModel.FIELDS_AFTER_SALARY_CHANGES, key = { it.id }) { field ->
                    NumberField(field, vm)
                }
                item {
                    Button(
                        onClick = vm::run,
                        modifier = Modifier
                            .padding(vertical = 12.dp)
                            .testTag(TestTags.RUN),
                    ) { Text("開始") }
                }
                items(vm.output) { line ->
                    Text(
                        line,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 12.sp,
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(Color(0xFFF9F9F9))
                            .padding(horizontal = 8.dp)
                            .testTag(TestTags.OUTPUT_LINE),
                    )
                }
            }
        }
    }
}

@Composable
private fun PrivacyNote() {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0xFFF0F8FF), RoundedCornerShape(4.dp))
            .padding(10.dp),
    ) {
        Text(
            "🔒 プライバシー重視: このアプリケーションはネットワーク通信をせずローカルで動くので安心してください。" +
                "あなたの財務情報が外部に送信されることはありません。",
            color = Color(0xFF666666),
            fontSize = 13.sp,
        )
    }
}

@Composable
private fun NumberField(field: InputField, vm: SimulatorViewModel) {
    OutlinedTextField(
        value = vm.value(field.id),
        onValueChange = { vm.setValue(field.id, it) },
        label = { Text(field.label) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(
            keyboardType = if (field.decimal) KeyboardType.Decimal else KeyboardType.Number,
        ),
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp)
            .testTag(field.id),
    )
}

@Composable
private fun SalaryChangePanel(vm: SimulatorViewModel) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp)
            .border(1.dp, Color(0xFFDDDDDD), RoundedCornerShape(5.dp))
            .background(Color(0xFFF9F9F9), RoundedCornerShape(5.dp))
            .padding(10.dp)
            .testTag(TestTags.SALARY_CHANGE_PANEL),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text("転職・昇進による給与変更", fontWeight = FontWeight.Bold, color = Color(0xFF333333))
        vm.salaryChanges.forEach { row ->
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedTextField(
                    value = row.age,
                    onValueChange = { vm.updateSalaryChange(row.copy(age = it)) },
                    label = { Text("年齢") },
                    placeholder = { Text("35") },
                    suffix = { Text("歳から") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier
                        .weight(1f)
                        .testTag(TestTags.SALARY_CHANGE_AGE),
                )
                OutlinedTextField(
                    value = row.salary,
                    onValueChange = { vm.updateSalaryChange(row.copy(salary = it)) },
                    label = { Text("年収") },
                    placeholder = { Text("4000000") },
                    suffix = { Text("円") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier
                        .weight(1.4f)
                        .testTag(TestTags.SALARY_CHANGE_SALARY),
                )
                Button(
                    onClick = { vm.removeSalaryChange(row.key) },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFF44336)),
                    modifier = Modifier.testTag(TestTags.SALARY_CHANGE_DELETE),
                ) { Text("削除") }
            }
        }
        Button(
            onClick = vm::addSalaryChange,
            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF4CAF50)),
            modifier = Modifier.testTag(TestTags.SALARY_CHANGE_ADD),
        ) { Text("➕ 給与変更を追加") }
    }
}
