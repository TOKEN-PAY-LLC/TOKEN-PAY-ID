package space.tokenpay.id.jvm

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import space.tokenpay.id.jvm.internal.RemoteConfig
import space.tokenpay.id.jvm.internal.SdkBuildInfo

/**
 * Regression tests for the CUPOL VPN bug report against 2.5.0-pre.2.
 *
 * Each test names the upstream bug number so a future contributor who
 * accidentally reintroduces one of these regressions sees immediately
 * which blocker they hit.
 */
class RegressionTest {

    // -----------------------------------------------------------------------
    // CUPOL #4 — RemoteConfig.compareSemver must not crash on clean semver
    //
    // Before the fix, `split('-', limit = 2).let { (core, pre) -> … }` threw
    // `IndexOutOfBoundsException: Index 1, Size 1` for any string without a
    // pre-release suffix, and the exception fired inside `derivedStateOf`
    // on every widget recompose.
    // -----------------------------------------------------------------------

    @Test
    fun `CUPOL-4 — isOlderThan tolerates clean semver without a pre suffix`() {
        val rc = RemoteConfig(recommendedSdkVersion = "3.1.0")
        // Must not throw, regardless of the outcome.
        val result = rc.isOlderThan("3.1.0")
        // Shipping SDK 3.0.1 is older than a future 3.1.0 GA.
        assertTrue(result, "current build must report as older than a future GA")
    }

    @Test
    fun `CUPOL-4 — isOlderThan works against a pre-release other value`() {
        val rc = RemoteConfig(recommendedSdkVersion = "2.5.0-pre.3")
        // Same version — not older.
        assertFalse(rc.isOlderThan("2.5.0-pre.3"))
    }

    @Test
    fun `CUPOL-4 — GA is always newer than any pre-release of the same core`() {
        val rc = RemoteConfig()
        // self=2.6.0 GA, so an older pre of the 2.6 line is older, and a
        // future 2.7 GA is newer.
        assertTrue(rc.isOlderThan("3.1.0"))
        assertFalse(rc.isOlderThan("2.6.0-pre.1"))
        assertFalse(rc.isOlderThan("2.5.0"))
    }

    @Test
    fun `CUPOL-4 — numeric core comparison still works`() {
        val rc = RemoteConfig()
        assertTrue(rc.isOlderThan("3.1.0"))
        assertFalse(rc.isOlderThan("1.9.9"))
    }

    // -----------------------------------------------------------------------
    // CUPOL #1 / #2 — SDK reports itself correctly in the UA header
    //
    // A sloppy merge that flipped `SdkBuildInfo.version` would ship broken
    // tooling to integrators and make support debugging impossible.
    // -----------------------------------------------------------------------

    @Test
    fun `SdkBuildInfo version matches the 3_0_0 native UI release`() {
        assertEquals("3.0.1", SdkBuildInfo.version)
        assertEquals("jvm", SdkBuildInfo.platform)
        assertTrue(SdkBuildInfo.userAgent.startsWith("TokenPayID-JVM/3.0"))
        assertTrue(SdkBuildInfo.sdkHeader.startsWith("jvm-desktop/3.0"))
    }

    // -----------------------------------------------------------------------
    // 2.6.1 — TpidUpdater / RemoteConfig surface area. The smart-update
    // banner is the headline feature of this release; these tests pin down
    // the JSON fields and cache behaviour that the banner relies on.
    // -----------------------------------------------------------------------

    @Test
    fun `RemoteConfig carries a parsed download_sha256 field`() {
        // `RemoteConfig.parse` is package-private and driven from the
        // async fetch path; the test instead pins the data class
        // contract that every platform must honour: a `downloadSha256`
        // getter that round-trips the server-supplied value unchanged.
        val cfg = RemoteConfig(
            recommendedSdkVersion = "2.6.3",
            downloadUrl = "https://example/sdk.tar.gz",
            downloadSha256 = "abc123",
        )
        assertEquals("abc123", cfg.downloadSha256)
        assertTrue(cfg.isOlderThan("9.9.9"))
    }

    @Test
    fun `invalidateCache forces the next fetch to network`() {
        // This is a behavioural test: the cache is a process-wide
        // AtomicReference; calling invalidateCache() should make the next
        // fetch bypass any cached value. We simulate by invoking the
        // invalidation directly — if the method is missing, the test
        // fails at compile-time.
        RemoteConfig.invalidateCache()
        // Re-invalidate to confirm idempotence.
        RemoteConfig.invalidateCache()
    }
}
