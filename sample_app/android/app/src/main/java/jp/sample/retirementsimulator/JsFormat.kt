package jp.sample.retirementsimulator

import java.math.BigDecimal
import java.math.RoundingMode
import java.text.DecimalFormat
import java.text.DecimalFormatSymbols
import java.util.Locale
import kotlin.math.abs
import kotlin.math.floor

/**
 * Web版(JavaScript)と同じ文字列を出すための数値の扱い。
 * 結果の行をWeb版と見比べられるよう、丸め方と表示の形をJavaScriptに合わせている。
 */
object JsFormat {

    /** JavaScript の Math.round と同じ。0.5ちょうどは正の方向に丸め、-0.5以上0未満は -0 になる */
    fun round(x: Double): Double {
        if (x.isNaN() || x.isInfinite()) return x
        val f = floor(x)
        val r = if (x - f >= 0.5) f + 1 else f
        return if (r == 0.0 && (x < 0 || 1 / x < 0)) -0.0 else r
    }

    /** JavaScript の Number.prototype.toLocaleString()(ja-JP)と同じ。3桁区切り、小数は3桁まで */
    fun toLocaleString(x: Double): String {
        if (x.isNaN()) return "NaN"
        if (x.isInfinite()) return if (x > 0) "∞" else "-∞"
        val negative = x < 0 || (x == 0.0 && 1 / x < 0)
        val format = DecimalFormat("#,##0.###", DecimalFormatSymbols(Locale.US)).apply {
            roundingMode = RoundingMode.HALF_UP
        }
        val body = format.format(BigDecimal(abs(x)))
        return if (negative) "-$body" else body
    }

    private val FLOAT_PREFIX = Regex("""^[+-]?(Infinity|(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?)""")

    /** JavaScript の parseFloat と同じ。先頭の数として読める部分だけを読み、読めなければ null(NaN) */
    fun parseFloat(text: String): Double? {
        val match = FLOAT_PREFIX.find(text.trimStart())?.value ?: return null
        return when (match.trimStart('+')) {
            "Infinity" -> Double.POSITIVE_INFINITY
            "-Infinity" -> Double.NEGATIVE_INFINITY
            else -> match.toDouble()
        }
    }

    /** JavaScript で数値を文字列に埋め込んだときと同じ。整数なら小数点を付けない */
    fun toJsString(x: Double): String =
        if (x == floor(x) && abs(x) < 1e21) x.toLong().toString() else x.toString()
}
