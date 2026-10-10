import android.os.SystemClock;
import android.view.InputDevice;
import android.view.InputEvent;
import android.view.MotionEvent;

import java.lang.reflect.Method;

/**
 * Shell-only bounded touch burst; does not load or modify the game.
 * The caller must verify the active scene and foreground before each invocation.
 * Injection acceptance is not proof that the game processed an attack.
 * Run with app_process and a dex-containing JAR, not as an APK.
 */
public final class RapidTouch {
    private static final int DEFAULT_X = 550;
    private static final int DEFAULT_Y = 800;
    private static final int MAX_TAPS = 12;
    private static final int MIN_INTERVAL_MS = 50;
    private static final int MAX_INTERVAL_MS = 1000;
    private static final int INJECT_ASYNC = 0;

    private RapidTouch() {}

    private static void inject(Object manager, Method injector, int action,
                               long downTime, long eventTime, int x, int y) throws Exception {
        MotionEvent event = MotionEvent.obtain(downTime, eventTime, action, x, y, 0);
        event.setSource(InputDevice.SOURCE_TOUCHSCREEN);
        try {
            if (!Boolean.TRUE.equals(injector.invoke(manager, event, INJECT_ASYNC))) {
                throw new IllegalStateException("Injection refused for action " + action);
            }
        } finally {
            event.recycle();
        }
    }

    public static void main(String[] args) throws Exception {
        if (args.length > 4 || args.length == 3) {
            throw new IllegalArgumentException("Usage: RapidTouch [taps 1..12] [intervalMs 50..1000] [x 400..750 y 700..1050]");
        }
        int taps = args.length > 0 ? Integer.parseInt(args[0]) : 8;
        int interval = args.length > 1 ? Integer.parseInt(args[1]) : 60;
        int x = args.length == 4 ? Integer.parseInt(args[2]) : DEFAULT_X;
        int y = args.length == 4 ? Integer.parseInt(args[3]) : DEFAULT_Y;
        if (x < 400 || x > 750 || y < 700 || y > 1050)
            throw new IllegalArgumentException("point must stay in the central scene region");
        if (taps < 1 || taps > MAX_TAPS || interval < MIN_INTERVAL_MS
                || interval > MAX_INTERVAL_MS) {
            throw new IllegalArgumentException("taps must be 1..12; intervalMs must be 50..1000");
        }

        Class<?> inputManager = Class.forName("android.hardware.input.InputManager");
        Method getter = inputManager.getDeclaredMethod("getInstance");
        getter.setAccessible(true);
        Object manager = getter.invoke(null);
        if (manager == null) {
            throw new IllegalStateException("InputManager unavailable");
        }
        Method injector = inputManager.getDeclaredMethod("injectInputEvent", InputEvent.class, int.class);
        injector.setAccessible(true);

        long began = SystemClock.uptimeMillis();
        long nextDown = began;
        for (int index = 0; index < taps; index++) {
            long remaining = nextDown - SystemClock.uptimeMillis();
            if (remaining > 0) {
                SystemClock.sleep(remaining);
            }
            long down = SystemClock.uptimeMillis();
            Exception failure = null;
            long up;
            try {
                inject(manager, injector, MotionEvent.ACTION_DOWN, down, down, x, y);
                SystemClock.sleep(5);
            } catch (Exception error) {
                failure = error;
            } finally {
                // Attempt release even when DOWN was refused or threw; never retry DOWN.
                up = SystemClock.uptimeMillis();
                try {
                    inject(manager, injector, MotionEvent.ACTION_UP, down, up, x, y);
                } catch (Exception error) {
                    if (failure == null) {
                        failure = error;
                    } else {
                        failure.addSuppressed(error);
                    }
                }
            }
            if (failure != null) {
                throw failure;
            }
            System.out.println("tap=" + (index + 1) + " down=" + down + " up=" + up
                    + " x=" + x + " y=" + y);
            nextDown = down + interval;
        }
        System.out.println("accepted=" + taps + " elapsedMs=" + (SystemClock.uptimeMillis() - began));
    }
}
