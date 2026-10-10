import com.vshower.instrumented.CdnCompressionMigration;
import java.nio.file.*;
import java.io.*;
import java.util.*;

/** Host-only failure/restart tests; all writes stay in a new private scratch root. */
public final class TestCdnCompressionMigration {
  static Path source,assets,root;
  static void check(boolean test,String message){if(!test)throw new AssertionError(message);}
  static Path fixture(String name)throws Exception {
    Path directory=root.resolve(name);Files.createDirectory(directory);Path target=directory.resolve("local/CDN.db");
    Files.createDirectories(target);
    try(java.util.stream.Stream<Path> paths=Files.list(source)) {
      for(Path path:(Iterable<Path>)paths::iterator) {
        String fileName=path.getFileName().toString();
        if(fileName.matches("CURRENT|MANIFEST-[0-9]+|[0-9]+\\.(ldb|log)"))Files.copy(path,target.resolve(path.getFileName()));
      }
    }
    for(String ancillary:Arrays.asList("LOCK","LOG","LOG.old"))
      Files.write(target.resolve(ancillary),("host-sentinel-"+ancillary).getBytes(java.nio.charset.StandardCharsets.US_ASCII));
    return directory;
  }
  static CdnCompressionMigration.Assets input(){return name->new FileInputStream(assets.resolve(name.substring(name.indexOf('/')+1)).toFile());}
  static boolean same(Path a,Path b)throws Exception{return Arrays.equals(Files.readAllBytes(a),Files.readAllBytes(b));}
  public static void main(String[] args)throws Exception {
    source=Paths.get(args[0]);assets=Paths.get(args[1]);Path privateRoot=Paths.get("recovered-assets/cdn-cache-20261010").toAbsolutePath().normalize();
    check(source.toAbsolutePath().normalize().startsWith(privateRoot),"private source required");
    root=Files.createTempDirectory(privateRoot,"migration-tests-");
    Path good=fixture("good");
    check(CdnCompressionMigration.migrate(good.toFile(),input()).equals("migrated-preserving-original"),"migration failed");
    Path backup=good.resolve("instrumentation/cdn-snappy-backup-v2");
    for(String name:Arrays.asList("CURRENT","MANIFEST-000436","000005.ldb","000010.ldb","000013.ldb","000016.ldb","000437.log","000438.ldb"))
      check(same(source.resolve(name),backup.resolve(name)),"original backup changed");
    for(String ancillary:Arrays.asList("LOCK","LOG","LOG.old"))
      check(Arrays.equals(Files.readAllBytes(backup.resolve(ancillary)),("host-sentinel-"+ancillary).getBytes(java.nio.charset.StandardCharsets.US_ASCII)),"ancillary backup changed");
    check(same(assets.resolve("000005.ldb"),good.resolve("local/CDN.db/000005.ldb")),"replacement differs");
    check(CdnCompressionMigration.migrate(good.toFile(),name->{throw new AssertionError("assets reopened after completion");}).equals("backup-preserved"),"repeat changed cache");
    Path mismatch=fixture("mismatch");Files.write(mismatch.resolve("local/CDN.db/000005.ldb"),new byte[]{1});
    check(CdnCompressionMigration.migrate(mismatch.toFile(),input()).equals("source-does-not-match"),"unknown cache modified");
    check(!Files.exists(mismatch.resolve("instrumentation/cdn-snappy-backup-v2")),"unknown cache backed up");
    Path missing=fixture("missing-assets");
    try{CdnCompressionMigration.migrate(missing.toFile(),name->{throw new IOException("missing test asset");});throw new AssertionError("missing asset accepted");}catch(IOException expected){}
    check(same(source.resolve("000005.ldb"),missing.resolve("local/CDN.db/000005.ldb")),"failed staging touched original");
    Path interrupted=fixture("interrupted");Files.createDirectories(interrupted.resolve("instrumentation"));
    Files.move(interrupted.resolve("local/CDN.db"),interrupted.resolve("instrumentation/cdn-snappy-backup-v2"));
    Files.createDirectory(interrupted.resolve("local/CDN.uncompressed-v2.stage"));
    Files.write(interrupted.resolve("local/CDN.uncompressed-v2.stage/unknown"),new byte[]{1});
    check(CdnCompressionMigration.migrate(interrupted.toFile(),input()).equals("restored-original-after-interruption"),"invalid stage prevented recovery");
    check(same(source.resolve("000005.ldb"),interrupted.resolve("local/CDN.db/000005.ldb")),"rollback lost original");
    Path resumed=fixture("resumed");Files.createDirectories(resumed.resolve("instrumentation"));
    Files.move(resumed.resolve("local/CDN.db"),resumed.resolve("instrumentation/cdn-snappy-backup-v2"));
    Path stage=resumed.resolve("local/CDN.uncompressed-v2.stage");Files.createDirectory(stage);
    try(java.util.stream.Stream<Path> paths=Files.list(good.resolve("local/CDN.db"))) {
      for(Path path:(Iterable<Path>)paths::iterator)Files.copy(path,stage.resolve(path.getFileName()));
    }
    check(CdnCompressionMigration.migrate(resumed.toFile(),input()).equals("resumed-promotion"),"valid stage not resumed");
    System.out.println("CDN migration: exact backup, repeat guard, mismatch, failed staging, rollback and interrupted promotion passed.");
  }
}
