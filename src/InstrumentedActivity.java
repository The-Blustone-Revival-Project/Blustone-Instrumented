package com.vshower.instrumented;

import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.view.MotionEvent;

import com.vshower.sr.MainActivity;

/** Keeps the original game activity while recording its lifecycle and input. */
public final class InstrumentedActivity extends MainActivity {
    @Override
    protected void attachBaseContext(Context base) {
        super.attachBaseContext(EnglishLocale.wrap(base));
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        Telemetry.activity("onCreate", this, state == null ? "fresh" : "restored");
    }

    @Override
    protected void onResume() {
        super.onResume();
        Telemetry.activity("onResume", this, null);
    }

    @Override
    protected void onPause() {
        Telemetry.activity("onPause", this, null);
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        Telemetry.activity("onDestroy", this, null);
        super.onDestroy();
    }

    @Override
    public boolean dispatchTouchEvent(MotionEvent event) {
        Telemetry.touch(this, event);
        return super.dispatchTouchEvent(event);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        Telemetry.activity("onWindowFocusChanged", this, Boolean.toString(hasFocus));
    }

    @Override
    public void onActivityResult(int requestCode, int resultCode, Intent data) {
        Telemetry.activityResult(this, requestCode, resultCode, data);
        super.onActivityResult(requestCode, resultCode, data);
    }
}
