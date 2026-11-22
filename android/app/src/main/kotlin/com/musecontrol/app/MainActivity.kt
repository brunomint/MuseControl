package com.musecontrol.app

import android.annotation.SuppressLint
import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.os.Environment
import android.webkit.URLUtil
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import org.json.JSONObject
import java.net.URLEncoder

/**
 * App do MuseControl: uma WebView em tela cheia com a página /pulso do
 * computador. A tela inicial (assets/inicio.html) acha o computador na rede.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var web: WebView
    private val prefs by lazy { getSharedPreferences("musecontrol", Context.MODE_PRIVATE) }

    // "Importar projeto…": a página pede um arquivo; o Android abre o seletor
    private var arquivoPedido: ValueCallback<Array<Uri>>? = null
    private val escolherArquivo = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        arquivoPedido?.onReceiveValue(if (uri != null) arrayOf(uri) else null)
        arquivoPedido = null
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) // tela não apaga
        web = WebView(this)
        web.setBackgroundColor(0xFF27272B.toInt())
        setContentView(web)
        telaCheia()

        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true // variáveis, tema, ajustes ficam no localStorage
            mediaPlaybackRequiresUserGesture = false
        }
        web.addJavascriptInterface(Ponte(), "AndroidMC")
        web.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                view: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams,
            ): Boolean {
                arquivoPedido?.onReceiveValue(null)
                arquivoPedido = callback
                escolherArquivo.launch("*/*")
                return true
            }
        }
        // "Exportar": o arquivo vai para a pasta Downloads do celular
        web.setDownloadListener { url, _, disposicao, tipo, _ ->
            val nome = URLUtil.guessFileName(url, disposicao, tipo)
            val pedido = DownloadManager.Request(Uri.parse(url))
                .setMimeType(tipo)
                .setTitle(nome)
                .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, nome)
            (getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager).enqueue(pedido)
            Toast.makeText(this, "Salvando $nome em Downloads", Toast.LENGTH_SHORT).show()
        }
        web.webViewClient = object : WebViewClient() {
            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                if (request.isForMainFrame && request.url.scheme != "file") {
                    abrirInicio("Perdi a conexão com o computador.")
                }
            }
        }

        // Voltar: fecha a janela aberta (⚙, 🛠…); se não houver, minimiza o app
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                web.evaluateJavascript("window.MuseControlVoltar ? window.MuseControlVoltar() : false") { r ->
                    if (r != "true") moveTaskToBack(true)
                }
            }
        })

        if (savedInstanceState == null) abrirInicio(null) else web.restoreState(savedInstanceState)
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) telaCheia()
    }

    private fun telaCheia() {
        WindowCompat.setDecorFitsSystemWindows(window, true)
        WindowInsetsControllerCompat(window, window.decorView).apply {
            hide(WindowInsetsCompat.Type.systemBars())
            systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }
    }

    /** Tela "Procurando o MuseControl…". [aviso] = mensagem; "trocar" = não reconectar sozinho. */
    private fun abrirInicio(aviso: String?) {
        val hash = if (aviso == null) "" else "#" + URLEncoder.encode(aviso, "UTF-8").replace("+", "%20")
        web.loadUrl("file:///android_asset/inicio.html$hash")
    }

    private fun js(codigo: String) = runOnUiThread { web.evaluateJavascript(codigo, null) }
    private fun texto(s: String) = JSONObject.quote(s) // string segura para o JavaScript

    /** O que a página pode pedir ao app (window.AndroidMC no JavaScript). */
    inner class Ponte {
        @JavascriptInterface
        fun ultimoServidor(): String = prefs.getString("servidor", "") ?: ""

        @JavascriptInterface
        fun procurar() = BuscaServidor.procurar(
            achou = { host -> js("window.mcAchou && mcAchou(${texto(host)})") },
            progresso = { f, t -> js("window.mcProgresso && mcProgresso($f, $t)") },
            fim = { n -> js("window.mcFim && mcFim($n)") },
        )

        @JavascriptInterface
        fun testar(host: String) {
            Thread {
                val ok = BuscaServidor.responde(host)
                js("window.mcTeste && mcTeste(${texto(BuscaServidor.comPorta(host))}, $ok)")
            }.start()
        }

        @JavascriptInterface
        fun abrir(host: String) {
            val h = BuscaServidor.comPorta(host)
            prefs.edit().putString("servidor", h).apply()
            runOnUiThread { web.loadUrl("http://$h/pulso") }
        }

        @JavascriptInterface
        fun trocarServidor() = runOnUiThread { abrirInicio("trocar") }

        @JavascriptInterface
        fun vibrar(ms: Int) {
            val v = if (Build.VERSION.SDK_INT >= 31) {
                (getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator
            } else {
                @Suppress("DEPRECATION")
                getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
            }
            val duracao = ms.coerceIn(1, 200).toLong()
            if (Build.VERSION.SDK_INT >= 26) {
                v.vibrate(VibrationEffect.createOneShot(duracao, VibrationEffect.DEFAULT_AMPLITUDE))
            } else {
                @Suppress("DEPRECATION")
                v.vibrate(duracao)
            }
        }

        @JavascriptInterface
        fun versao(): String = packageManager.getPackageInfo(packageName, 0).versionName ?: ""
    }
}
