package com.vshower.instrumented;

import android.content.Context;
import java.io.File;
import java.io.FileInputStream;
import java.security.MessageDigest;
import java.util.HashMap;
import java.util.Map;
import org.json.JSONArray;
import org.json.JSONObject;

/** Fixed public JET inventory only: metadata/digests, never contents or account
 * files. Hashes are cached by size/mtime after two equal samples. No writes,
 * repairs, native calls or uploads of resource bytes. */
final class EpisodeResourceSnapshot {
    private static final String[][] ORIGINALS = {
        {"R_EPISODE.jet","38080","7f4362cdf80545a6da937444094837f334c8aae4f9f791d6ff4161948d98a01e"},
        {"EPISODE.jet","6529928","7bc7b12c57847e690648286170167b2d14ab9207d6df21d35c87f7c6b909ed30"},
        {"DIAL-EN.jet","3133395","a79ea5c803b1dc747a052e5a438c521e4e5617932d67990d6ec4d44e75a3a3c0"},
        {"N001_BG.jet","2282467","4d09c9eaf150befb7adc3a32919bdba6247ceb2097d5cac069de5da48fcb3d40"},
        {"ST099.jet","1252287","e99d2c7df04f4c32f539d4b79d44791a69f97046dd61b48d4a89211a72f50e81"},
        {"SND1.jet","7173961","4c0e83adbfc401c19be6bbc331cf3a97b248fb837208c0717a13d5728f81c5c2"},
        {"SND_CDN.jet","10911430","a9a2cfe2250ba21c1cca953b4e1a115a2a2c06290b0c4b06e4a42f3bffb232f7"},
        {"VOICE_CDN2.jet","5245246","3effe37762d25055eb5043dd1db8aca0fafb7fd3bb07618624d5cb481f42f692"},
        {"VOICE_CDN6.jet","7338509","6e1fc70711557d03a2eec6b02fae393f52d510c408b0f732237b19ca794a1c2e"},
        {"C009.jet","3101288","98dc7e66efc1f3b4453966cf6ed09f1cab20af12b158eed1b51355b8cec798c5"},
        {"C009_Q.jet","50218","ba7951cd2d2f0bab3b69021d5250c270b81130b3ee80c8bd375664139382549c"},
        {"C009_EFT.jet","1616214","70af98a2c1781f84b05dba6cc462affcb5d18df88d97f3d922c8ad33267f84cf"},
        {"C009_SND.jet","142949","fb11b78c034d6051c9341fc3c1dcd76c4888f874acbc8fad9b32d39163551635"}
    };
    private static final class Entry {
        long size, modified;
        String digest;
        Entry(long size,long modified) { this.size=size; this.modified=modified; }
    }
    private static final Map<String,Entry> CACHE = new HashMap<>();

    static JSONObject capture(Context context) {
        JSONObject result = new JSONObject();
        try {
            if (!"com.vshower.prd_sr.instrumented".equals(context.getPackageName()) ||
                context.getPackageManager().getPackageInfo(context.getPackageName(),0).versionCode != 28010) {
                result.put("status","wrong_package_or_version"); return result;
            }
            File declaredDirectory = new File(context.getFilesDir().getCanonicalFile(), "local");
            File directory = declaredDirectory.getCanonicalFile();
            if (!declaredDirectory.equals(directory)) throw new IllegalStateException("directory_guard");
            JSONArray files = new JSONArray(); int matched = 0;
            for (String[] original:ORIGINALS) {
                String name=original[0]; long expected=Long.parseLong(original[1]);
                JSONObject row=new JSONObject(); row.put("name",name);
                try {
                    File file = new File(directory,name).getCanonicalFile();
                    if (!directory.equals(file.getParentFile())) throw new IllegalStateException("path_guard");
                    if (!file.isFile()) { CACHE.remove(name); row.put("status","missing"); }
                    else {
                        long size=file.length(),modified=file.lastModified(); row.put("bytes",size);
                        if (size!=expected) { CACHE.remove(name); row.put("status","size_mismatch"); }
                        else {
                            Entry entry=CACHE.get(name);
                            if (entry==null || entry.size!=size || entry.modified!=modified) {
                                CACHE.put(name,new Entry(size,modified)); row.put("status","waiting_stable_metadata");
                            } else {
                                boolean cached = entry.digest!=null;
                                if (entry.digest==null) {
                                    MessageDigest digest=MessageDigest.getInstance("SHA-256");
                                    byte[] buffer=new byte[16384]; long total=0;
                                    try (FileInputStream stream=new FileInputStream(file)) {
                                        int count;
                                        while ((count=stream.read(buffer))!=-1) {
                                            total+=count; if (total>expected) throw new IllegalStateException("size_changed");
                                            digest.update(buffer,0,count);
                                        }
                                    }
                                    if (total!=size || file.length()!=size || file.lastModified()!=modified)
                                        throw new IllegalStateException("unstable");
                                    StringBuilder hex=new StringBuilder(64);
                                    for (byte value:digest.digest()) { int v=value&255; if(v<16)hex.append('0');hex.append(Integer.toHexString(v)); }
                                    entry.digest=hex.toString();
                                }
                                if (file.length()!=size || file.lastModified()!=modified) throw new IllegalStateException("unstable");
                                boolean matches=original[2].equals(entry.digest);
                                row.put("status","hashed"); row.put("sha256",entry.digest); row.put("matches_original",matches);
                                row.put("hash_cached",cached);
                                if(matches)matched++;
                            }
                        }
                    }
                } catch(Exception unavailable) { CACHE.remove(name); row=new JSONObject();row.put("name",name);row.put("status","unavailable"); }
                files.put(row);
            }
            result.put("status","observed");result.put("files",files);result.put("originals_matched",matched);
        } catch(Exception unavailable) {
            try { result=new JSONObject();result.put("status","unavailable"); } catch(Exception ignored) {}
        }
        return result;
    }
}
