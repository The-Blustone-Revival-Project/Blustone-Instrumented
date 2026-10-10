package com.vshower.instrumented;

import java.io.*;
import java.security.MessageDigest;
import java.util.*;

/** One-time, pre-native migration of the exact diagnosed instrumented cache.
 * No database opens, deletions, account reads or synthesized resource metadata.
 * The complete original directory is retained; only table5 and its manifest
 * file-size edit change. Live encrypted records never become bundled assets. */
public final class CdnCompressionMigration {
    public interface Assets { InputStream open(String name) throws Exception; }
    private static final String EMPTY="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
    private static final Map<String,String> ORIGINAL=new LinkedHashMap<String,String>();
    private static final Map<String,String> REPAIRED=new LinkedHashMap<String,String>();
    static {
        ORIGINAL.put("CURRENT","9f0c6321744d98ade9090a16c9bda487abfc9217aab911db5618bfd4c92c3180");
        ORIGINAL.put("MANIFEST-000436","bd49077f14c0c09fd085a89eb860ce2e3fafbfa2eb99151f2c60401fa55c6c8c");
        ORIGINAL.put("000005.ldb","5382476369667922e6e85750035cb5ba080b1a4af2da06dfab250768c149da48");
        ORIGINAL.put("000010.ldb","6a809100e01b517069c55f4c744fb3e9201a8295a0669c3afcf2e7ddfd6403d8");
        ORIGINAL.put("000013.ldb","d25d85542d2e50f3b7069c749622f74bf2b35091fd8bb589424cfb1d00e1657e");
        ORIGINAL.put("000016.ldb","48a4641b869e0d6a71a227e842145c64395d2c29ea6e64b86b803435685612ac");
        ORIGINAL.put("000437.log",EMPTY);
        // Failed compaction output is outside the active manifest. Preserve
        // it byte-for-byte with the rest of the diagnosed directory.
        ORIGINAL.put("000438.ldb","c47e7490318418d61403829577bd4b2225b85181f6f97d15fb732fb6d610ba4c");
        REPAIRED.putAll(ORIGINAL);
        REPAIRED.put("000005.ldb","5382476369667922e6e85750035cb5ba080b1a4af2da06dfab250768c149da48");
        REPAIRED.put("MANIFEST-000436","2cb5faf243ade5655385a3d77ff31b59f17bcd4d05227277480d65970ef24868");
    }
    private static String hash(File file) throws Exception {
        if(!file.isFile() || file.length()>1048576) throw new IOException("cache file unavailable/outside bound");
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        try(InputStream input=new FileInputStream(file)) {
            byte[] buffer=new byte[16384];int count;
            while((count=input.read(buffer))!=-1)digest.update(buffer,0,count);
        }
        StringBuilder text=new StringBuilder();
        for(byte value:digest.digest())text.append(String.format(Locale.US,"%02x",value&255));
        return text.toString();
    }
    private static Map<String,String> inventory(File directory) throws Exception {
        File[] files=directory.listFiles();
        if(files==null || files.length>16)throw new IOException("cache inventory unavailable/outside bound");
        Map<String,String> result=new TreeMap<String,String>();
        for(File file:files) {
            String name=file.getName();
            if(!ORIGINAL.containsKey(name) && !name.equals("LOCK") && !name.equals("LOG") && !name.equals("LOG.old"))
                throw new IOException("unrecognized cache inventory");
            if(!file.getCanonicalFile().getParentFile().equals(directory.getCanonicalFile()))
                throw new IOException("cache file path escaped directory");
            result.put(name,hash(file));
        }
        return result;
    }
    private static boolean matches(File directory,Map<String,String> expected) throws Exception {
        if(!directory.isDirectory())return false;
        Map<String,String> actual=inventory(directory);
        for(Map.Entry<String,String> row:expected.entrySet())
            if(!row.getValue().equals(actual.get(row.getKey())))return false;
        return true;
    }
    private static void copy(InputStream input,File destination) throws Exception {
        try(InputStream source=input;FileOutputStream output=new FileOutputStream(destination)) {
            byte[] buffer=new byte[16384];int count,total=0;
            while((count=source.read(buffer))!=-1) {
                total+=count;if(total>1048576)throw new IOException("cache copy outside bound");
                output.write(buffer,0,count);
            }
            output.getFD().sync();
        }
    }
    public static String migrate(File files,Assets assets) throws Exception {
        File local=new File(files,"local"),telemetry=new File(files,"instrumentation");
        File current=new File(local,"CDN.db"),stage=new File(local,"CDN.uncompressed-v2.stage");
        File backup=new File(telemetry,"cdn-snappy-backup-v2");
        if(!current.getCanonicalFile().getParentFile().equals(local.getCanonicalFile()) ||
           !stage.getCanonicalFile().getParentFile().equals(local.getCanonicalFile()) ||
           !backup.getCanonicalFile().getParentFile().equals(telemetry.getCanonicalFile()))
            throw new IOException("cache migration path guard failed");
        if(backup.exists()) {
            // An evolved native cache must never be replaced on later boots.
            if(current.exists())return "backup-preserved";
            try {
                if(matches(stage,REPAIRED) && stage.renameTo(current))return "resumed-promotion";
            } catch(Exception invalidStage) { /* Recover the preserved original below. */ }
            if(backup.renameTo(current))return "restored-original-after-interruption";
            throw new IOException("interrupted migration needs preserved backup recovery");
        }
        if(!matches(current,ORIGINAL))return "source-does-not-match";
        Map<String,String> before=inventory(current);
        if(!stage.exists()) {
            if(!stage.mkdir())throw new IOException("migration staging creation failed");
            for(String name:before.keySet())copy(new FileInputStream(new File(current,name)),new File(stage,name));
            for(String name:Arrays.asList("000005.ldb","MANIFEST-000436"))
                copy(assets.open("instrumented-cdn-uncompressed-v1/"+name),new File(stage,name));
        }
        if(!matches(stage,REPAIRED) || !inventory(current).equals(before))
            throw new IOException("migration stage/source verification failed");
        if(!telemetry.isDirectory() && !telemetry.mkdirs())throw new IOException("backup parent creation failed");
        if(backup.exists() || !current.renameTo(backup))throw new IOException("preserving original cache failed");
        boolean promoted=false;
        try {
            if(!inventory(backup).equals(before))throw new IOException("preserved cache verification failed");
            if(current.exists() || !stage.renameTo(current))
                throw new IOException("migration promotion failed; original retained");
            promoted=true;
            if(!matches(current,REPAIRED))throw new IOException("promoted cache verification failed");
        } catch(Exception failure) {
            if(promoted && current.exists() && (stage.exists() || !current.renameTo(stage)))
                throw new IOException("migration held; replacement and original preserved",failure);
            if(!current.exists() && !backup.renameTo(current))
                throw new IOException("migration held; preserved original requires recovery",failure);
            throw failure;
        }
        return "migrated-preserving-original";
    }
}
