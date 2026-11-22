package jp.sample.retirementsimulator

import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.test.performTextReplacement
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * 画面の入力が計算に渡り、結果が画面に出るまでの配線を確かめる(エミュレータか実機で動かす)。
 * DEX の制約でテスト名に空白を使えないため、区切りは _ にしている。
 */
@RunWith(AndroidJUnit4::class)
class RetirementSimulatorScreenTest {

    @get:Rule
    val compose = createComposeRule()

    private lateinit var viewModel: SimulatorViewModel

    @Before
    fun setUp() {
        viewModel = SimulatorViewModel()
        compose.setContent { RetirementSimulatorScreen(viewModel) }
    }

    /**
     * 結果にこの行があることを確かめる。結果の行は画面に入った分しか作られないので、
     * その行までスクロールする(行が無ければスクロールが失敗する)。同じ文の行は何か月分もあるので先頭を見る
     */
    private fun assertOutputLine(text: String) {
        compose.onNodeWithTag(TestTags.SCREEN).performScrollToNode(hasText(text))
        compose.onAllNodesWithText(text).onFirst().assertIsDisplayed()
    }

    /** 画面の部品も画面に入った分しか作られない。端末の画面の大きさで変わるので、触る前に必ずそこまでスクロールする */
    private fun scrollToTag(tag: String) {
        compose.onNodeWithTag(TestTags.SCREEN).performScrollToNode(hasTestTag(tag))
    }

    private fun tap(tag: String) {
        scrollToTag(tag)
        compose.onNodeWithTag(tag).performClick()
    }

    private fun input(tag: String, text: String) {
        scrollToTag(tag)
        compose.onNodeWithTag(tag).performTextReplacement(text)
    }

    @Test
    fun 開始を押すと開始年齢から月ごとの結果を出す() {
        tap(TestTags.RUN)
        assertOutputLine("-- 30歳1月 --")
    }

    @Test
    fun 入力した開始年齢と生活費で計算する() {
        input("startAge", "99")
        input("retirementAge", "99")
        input("pensionStartAge", "99")
        input("expenseRetired", "1000")
        input("eventProb", "0")
        tap(TestTags.RUN)
        assertOutputLine("-- 99歳1月 --")
        assertOutputLine("  年金: ¥145,000")
        assertOutputLine("  生活費: ¥1,000")
    }

    @Test
    fun 給与変更は表示切り替えで出し入れでき追加と削除ができる() {
        compose.onAllNodesWithTag(TestTags.SALARY_CHANGE_ADD).assertCountEquals(0)
        tap(TestTags.SALARY_CHANGE_TOGGLE)
        tap(TestTags.SALARY_CHANGE_ADD)
        tap(TestTags.SALARY_CHANGE_ADD)
        compose.onAllNodesWithTag(TestTags.SALARY_CHANGE_DELETE).assertCountEquals(2)
        compose.onAllNodesWithTag(TestTags.SALARY_CHANGE_DELETE)[0].performClick()
        compose.onAllNodesWithTag(TestTags.SALARY_CHANGE_DELETE).assertCountEquals(1)
        tap(TestTags.SALARY_CHANGE_TOGGLE)
        compose.onAllNodesWithTag(TestTags.SALARY_CHANGE_ADD).assertCountEquals(0)
    }

    @Test
    fun 給与変更を入れるとその年齢から年収が変わったことを結果に出す() {
        tap(TestTags.SALARY_CHANGE_TOGGLE)
        tap(TestTags.SALARY_CHANGE_ADD)
        input(TestTags.SALARY_CHANGE_AGE, "31")
        input(TestTags.SALARY_CHANGE_SALARY, "4000000")
        input("eventProb", "0")
        tap(TestTags.RUN)
        // 開始年齢30歳のまま。年収400万円の手取りは月245,458円、その20%を投資に回す
        assertOutputLine("  給与: ¥245,458 (投資: ¥49,092) [年収: ¥4,000,000]")
    }
}
