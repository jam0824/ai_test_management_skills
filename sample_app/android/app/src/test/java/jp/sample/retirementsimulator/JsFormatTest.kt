package jp.sample.retirementsimulator

import org.junit.Assert.assertEquals
import org.junit.Test

/** Web版(JavaScript)と同じ見た目で数値を出せるかを確かめる */
class JsFormatTest {

    @Test
    fun `整数は3桁ごとにカンマで区切る`() {
        assertEquals("1,234,567", JsFormat.toLocaleString(1234567.0))
    }

    @Test
    fun `小数は3桁まで出し、4桁目を四捨五入する`() {
        assertEquals("1,234.568", JsFormat.toLocaleString(1234.5678))
    }

    @Test
    fun `小数の末尾の0は出さない`() {
        assertEquals("12.5", JsFormat.toLocaleString(12.5))
    }

    @Test
    fun `負の数は先頭にマイナスを付ける`() {
        assertEquals("-1,000", JsFormat.toLocaleString(-1000.0))
    }

    @Test
    fun `マイナスゼロはJavaScriptと同じくマイナス0と出す`() {
        assertEquals("-0", JsFormat.toLocaleString(-0.0))
    }

    @Test
    fun `四捨五入はJavaScriptのMath_roundと同じく正の方向に丸める`() {
        assertEquals(3.0, JsFormat.round(2.5), 0.0)
        assertEquals(-2.0, JsFormat.round(-2.5), 0.0)
        assertEquals(-3.0, JsFormat.round(-2.6), 0.0)
    }

    @Test
    fun `マイナス0_5以上0未満を丸めるとマイナスゼロになる`() {
        assertEquals("-0", JsFormat.toLocaleString(JsFormat.round(-0.3)))
    }

    @Test
    fun `入力はparseFloatと同じく先頭の数として読める部分だけを読む`() {
        assertEquals(12.0, JsFormat.parseFloat("12abc")!!, 0.0)
        assertEquals(1.0, JsFormat.parseFloat("1,000")!!, 0.0)
        assertEquals(0.5, JsFormat.parseFloat(" .5")!!, 0.0)
        assertEquals(-1500.0, JsFormat.parseFloat("-1.5e3")!!, 0.0)
    }

    @Test
    fun `数として読めない入力はnullを返す`() {
        assertEquals(null, JsFormat.parseFloat(""))
        assertEquals(null, JsFormat.parseFloat("abc"))
    }

    @Test
    fun `整数の年齢は小数点を付けずに文字列にする`() {
        assertEquals("30", JsFormat.toJsString(30.0))
        assertEquals("30.5", JsFormat.toJsString(30.5))
    }
}
