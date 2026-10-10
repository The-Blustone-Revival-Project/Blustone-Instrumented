import java.lang.reflect.Method;

/** Shell-only Android 7 helper for its missing pm install-existing command.
 * Registers the unchanged existing instrumented APK for the pre-created test
 * user10. Never reinstalls/replaces APK code or clears application data. */
public final class RegisterExistingResearchPackage {
  public static void main(String[] args) throws Exception {
    if (args.length != 1 || !"10".equals(args[0]))
      throw new IllegalArgumentException("Only the pre-created research user10 is permitted");
    final String pkg = "com.vshower.prd_sr.instrumented";
    Class<?> manager = Class.forName("android.os.ServiceManager");
    Object binder = manager.getMethod("getService", String.class).invoke(null, "package");
    if (binder == null) throw new IllegalStateException("Package service unavailable");
    Object service = Class.forName("android.content.pm.IPackageManager$Stub")
      .getMethod("asInterface", Class.forName("android.os.IBinder")).invoke(null, binder);
    Method install = Class.forName("android.content.pm.IPackageManager")
      .getMethod("installExistingPackageAsUser", String.class, int.class);
    int result = ((Integer) install.invoke(service, pkg, 10)).intValue();
    System.out.println("Existing instrumented package registration for user10 returned " + result);
    if (result != 1) throw new IllegalStateException("Registration refused; no replacement fallback");
  }
}
