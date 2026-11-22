package com.musecontrol.app

import java.net.HttpURLConnection
import java.net.Inet4Address
import java.net.NetworkInterface
import java.net.URL
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

/**
 * Procura o computador com o MuseControl na rede Wi-Fi: testa cada endereço
 * da rede (ex.: 192.168.0.1 a 192.168.0.254) em http://IP:8888/pulso/ping.
 */
object BuscaServidor {

    const val PORTA = 8888
    private const val TEMPO_MS = 800

    /** "192.168.0.23" -> "192.168.0." ; ignora o que não é IPv4 de rede local. */
    fun prefixoDaRede(ip: String): String? {
        val partes = ip.split(".")
        if (partes.size != 4 || partes.any { it.toIntOrNull() !in 0..255 }) return null
        val a = partes[0].toInt()
        val b = partes[1].toInt()
        val local = a == 10 || (a == 172 && b in 16..31) || (a == 192 && b == 168)
        return if (local) "${partes[0]}.${partes[1]}.${partes[2]}." else null
    }

    /** Endereços a testar em cada rede do aparelho (sem o próprio aparelho). */
    fun candidatos(ipsDoAparelho: List<String>): List<String> {
        val lista = LinkedHashSet<String>()
        for (ip in ipsDoAparelho) {
            val prefixo = prefixoDaRede(ip) ?: continue
            for (n in 1..254) lista.add(prefixo + n)
        }
        lista.removeAll(ipsDoAparelho.toSet()) // nenhum endereço do próprio celular
        return lista.toList()
    }

    /** "192.168.0.7" -> "192.168.0.7:8888"; "192.168.0.7:9000" fica como está. */
    fun comPorta(host: String): String {
        val h = host.trim().removePrefix("http://").trimEnd('/')
        return if (h.contains(":")) h else "$h:$PORTA"
    }

    fun ipsDoAparelho(): List<String> =
        NetworkInterface.getNetworkInterfaces().toList()
            .filter { it.isUp && !it.isLoopback }
            .flatMap { it.inetAddresses.toList() }
            .filterIsInstance<Inet4Address>()
            .map { it.hostAddress ?: "" }
            .filter { prefixoDaRede(it) != null }

    /** O endereço responde como um MuseControl? */
    fun responde(host: String): Boolean = try {
        val con = URL("http://${comPorta(host)}/pulso/ping").openConnection() as HttpURLConnection
        con.connectTimeout = TEMPO_MS
        con.readTimeout = TEMPO_MS
        try {
            con.responseCode == 200 && con.inputStream.bufferedReader().readText().contains("\"ok\"")
        } finally {
            con.disconnect()
        }
    } catch (e: Exception) {
        false
    }

    /**
     * Testa todos os candidatos em paralelo. Chama [achou] para cada MuseControl,
     * [progresso] conforme avança e [fim] com o total achado.
     */
    fun procurar(
        achou: (String) -> Unit,
        progresso: (Int, Int) -> Unit,
        fim: (Int) -> Unit,
    ) {
        Thread {
            val alvos = candidatos(ipsDoAparelho())
            if (alvos.isEmpty()) {
                fim(0)
                return@Thread
            }
            val pool = Executors.newFixedThreadPool(64)
            val feitos = AtomicInteger(0)
            val achados = AtomicInteger(0)
            for (ip in alvos) {
                pool.execute {
                    if (responde(ip)) {
                        achados.incrementAndGet()
                        achou(comPorta(ip))
                    }
                    val f = feitos.incrementAndGet()
                    if (f % 16 == 0 || f == alvos.size) progresso(f, alvos.size)
                }
            }
            pool.shutdown()
            pool.awaitTermination(60, TimeUnit.SECONDS)
            fim(achados.get())
        }.start()
    }
}
