"""Read-only validation of migrated build paths; never builds or installs an APK."""
from pathlib import Path
import importlib.util,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('instrumented_builder',ROOT/'tools/build-instrumented-apk.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
names=['BASE_APK','TRACE_SO','NATIVE_CORE_OVERRIDE','APKTOOL','AAPT2','ZIPALIGN','APKSIGNER','ANDROID_JAR','JAVAC','JAVA','D8','KEYSTORE']
for name in names:
    p=Path(getattr(builder,name)).resolve()
    assert p.is_relative_to(ROOT.resolve()),f'{name} points outside this repository'
    assert p.is_file(),f'{name} missing: {p.relative_to(ROOT)}'
for name in ['SOURCES','STUBS','EXTRA_ASSETS']:
    p=Path(getattr(builder,name));assert p.is_dir(),name
assert list(builder.SOURCES.rglob('*.java')) and list(builder.STUBS.rglob('*.java'))
print(json.dumps({'repo_local_build_inputs':len(names),'client_java_sources':len(list(builder.SOURCES.rglob('*.java'))),
                  'signing_key_present':True,'apk_rebuilt':False,'installed':False}))
