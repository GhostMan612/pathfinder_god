// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network;

import java.security.cert.Certificate;
import java.util.List;
import okhttp3.OkHttpClient;
import okhttp3.internal.tls.CertificateChainCleaner;

/**
 * JVM compatibility helper to configure OkHttp's CertificateChainCleaner
 * for self-signed certificate pinning.
 */
public final class OkHttpTlsCompat {
    private OkHttpTlsCompat() {}

    public static void setPassThroughCertificateChainCleaner(OkHttpClient.Builder builder) {
        builder.setCertificateChainCleaner$okhttp(new CertificateChainCleaner() {
            @Override
            @SuppressWarnings("unchecked")
            public List<Certificate> clean(List<? extends Certificate> chain, String hostname) {
                return (List<Certificate>) chain;
            }
        });
    }
}
