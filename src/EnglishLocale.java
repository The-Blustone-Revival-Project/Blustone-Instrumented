package com.vshower.instrumented;

import android.content.Context;
import android.content.res.Configuration;
import android.os.Build;

import java.util.Locale;

/** Forces English only inside the instrumented side-by-side package. */
public final class EnglishLocale {
    private EnglishLocale() {}

    public static Context wrap(Context base) {
        Configuration configuration = new Configuration(base.getResources().getConfiguration());
        apply(configuration);
        return base.createConfigurationContext(configuration);
    }

    public static void apply(Context context) {
        Configuration configuration = new Configuration(context.getResources().getConfiguration());
        apply(configuration);
        context.getResources().updateConfiguration(configuration, context.getResources().getDisplayMetrics());
    }

    private static void apply(Configuration configuration) {
        Locale english = Locale.US;
        if (Build.VERSION.SDK_INT >= 24) {
            configuration.setLocales(new android.os.LocaleList(english));
        } else if (Build.VERSION.SDK_INT >= 17) {
            configuration.setLocale(english);
        } else {
            configuration.locale = english;
        }
    }
}

