package com.musecontrol.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class BuscaServidorTest {

    @Test
    fun prefixoSoDeRedeLocal() {
        assertEquals("192.168.0.", BuscaServidor.prefixoDaRede("192.168.0.5"))
        assertEquals("10.0.2.", BuscaServidor.prefixoDaRede("10.0.2.16"))
        assertEquals("172.20.1.", BuscaServidor.prefixoDaRede("172.20.1.9"))
        assertNull(BuscaServidor.prefixoDaRede("8.8.8.8"))       // internet, não rede de casa
        assertNull(BuscaServidor.prefixoDaRede("172.32.0.1"))    // fora da faixa privada
        assertNull(BuscaServidor.prefixoDaRede("100.105.155.13")) // Tailscale: não varre
        assertNull(BuscaServidor.prefixoDaRede("fe80::1"))
    }

    @Test
    fun candidatosSemOProprioAparelho() {
        val c = BuscaServidor.candidatos(listOf("192.168.0.5"))
        assertEquals(253, c.size)
        assertFalse("192.168.0.5" in c)
        assertTrue("192.168.0.7" in c)
        assertEquals("192.168.0.1", c.first())
        assertEquals("192.168.0.254", c.last())
    }

    @Test
    fun duasRedesSemRepetir() {
        // dois endereços na mesma rede + outra rede: nenhum endereço do próprio aparelho
        val c = BuscaServidor.candidatos(listOf("192.168.0.5", "10.0.0.3", "192.168.0.9"))
        assertEquals(252 + 253, c.size)
        assertEquals(c.size, c.toSet().size)
        assertFalse("192.168.0.5" in c || "192.168.0.9" in c || "10.0.0.3" in c)
    }

    @Test
    fun portaPadrao() {
        assertEquals("192.168.0.7:8888", BuscaServidor.comPorta("192.168.0.7"))
        assertEquals("192.168.0.7:8888", BuscaServidor.comPorta(" http://192.168.0.7/ "))
        assertEquals("192.168.0.7:9000", BuscaServidor.comPorta("192.168.0.7:9000"))
    }
}
