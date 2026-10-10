package com.vshower.instrumented;

import android.content.Context;

import androidx.multidex.MultiDexApplication;

/** Separate application entry point for the side-by-side diagnostic APK. */
public final class InstrumentedApplication extends MultiDexApplication {
    @Override
    protected void attachBaseContext(Context base) {
        super.attachBaseContext(EnglishLocale.wrap(base));
    }

    @Override
    public void onCreate() {
        super.onCreate();
        EnglishLocale.apply(this);
        Telemetry.install(this);
    }
}
