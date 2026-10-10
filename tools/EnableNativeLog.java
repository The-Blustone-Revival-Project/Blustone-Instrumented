import com.sun.jdi.*;
import com.sun.jdi.connect.*;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;

/** Enable the game's existing diagnostic switch on a debug APK via forwarded JDWP. */
public class EnableNativeLog {
  public static void main(String[] args) throws Exception {
    AttachingConnector connector = Bootstrap.virtualMachineManager().attachingConnectors().stream()
      .filter(c -> c.name().equals("com.sun.jdi.SocketAttach")).findFirst().orElseThrow();
    var config = connector.defaultArguments();
    config.get("hostname").setValue("127.0.0.1");
    config.get("port").setValue(args.length > 0 ? args[0] : "8701");
    VirtualMachine vm = connector.attach(config);
    try {
      ReferenceType activity = vm.classesByName("android.app.Activity").get(0);
      var breakpoint = vm.eventRequestManager().createBreakpointRequest(
        activity.methodsByName("dispatchTouchEvent").get(0).location());
      breakpoint.setSuspendPolicy(EventRequest.SUSPEND_ALL);
      breakpoint.enable();
      System.out.println("Waiting up to 30 seconds for an ADB tap in the game activity.");
      long deadline = System.currentTimeMillis() + 30000;
      while (System.currentTimeMillis() < deadline) {
        EventSet events = vm.eventQueue().remove(1000);
        if (events == null) continue;
        for (Event event : events) {
          if (event instanceof BreakpointEvent hit) {
            breakpoint.disable();
            ClassType jni = (ClassType)vm.classesByName("com.vshower.rann.RMJNIMethod").get(0);
            jni.invokeMethod(hit.thread(), jni.methodsByName("JNISetDebugLevel").get(0),
              java.util.List.of(vm.mirrorOf(0)), ClassType.INVOKE_SINGLE_THREADED);
            events.resume();
            System.out.println("Enabled RMDBG_LOG(FULL).");
            return;
          }
        }
        events.resume();
      }
      throw new IllegalStateException("No activity tap breakpoint observed");
    } finally { vm.dispose(); }
  }
}
