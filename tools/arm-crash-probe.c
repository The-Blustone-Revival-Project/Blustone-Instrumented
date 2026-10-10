/* Local emulator diagnostic only. Does not alter game data or game branches. */
#define _GNU_SOURCE
#include <android/log.h>
#include <dlfcn.h>
#include <jni.h>
#include <errno.h>
#include <stdint.h>
#include <string.h>
#include <sys/mman.h>
#include <signal.h>
#include <pthread.h>
#include <ucontext.h>
#include <unistd.h>
#include <unwind.h>

static volatile sig_atomic_t installed;
static uintptr_t game_start, game_end;

/*
 * The game uses libc++'s 32-bit basic_string layout.  The first byte is the
 * short-string length*2, or has bit 0 set for a long string.  In the long
 * representation the data pointer is at offset 0 and the length at offset 4;
 * the short representation stores bytes inline at offset 1.  This reader is
 * deliberately bounded and only observes arguments supplied by the game.
 */
static int read_game_string(const void *object, char *out, size_t capacity) {
    const uint8_t *bytes = (const uint8_t *)object;
    const char *data;
    uint32_t length;

    if (!object || !out || capacity < 2) return 0;
    if (bytes[0] & 1) {
        length = *(const uint32_t *)(bytes + 4);
        data = *(const char * const *)(bytes + 0);
    } else {
        length = (uint32_t)(bytes[0] >> 1);
        data = (const char *)bytes + 1;
    }
    if (!data || length > 4096) return 0;
    if (length >= capacity) length = (uint32_t)capacity - 1;
    memcpy(out, data, length);
    out[length] = '\0';
    return 1;
}

static int relevant_db_key(const char *value) {
    if (!value) return 0;
    return strstr(value, "SR_") || strstr(value, "UI_") || strstr(value, "E_") ||
           strstr(value, "stage") || strstr(value, "Stage") || strstr(value, "STAGE") ||
           strstr(value, "area") || strstr(value, "Area") || strstr(value, "AREA") ||
           strstr(value, "mission") || strstr(value, "Mission") || strstr(value, "MISSION") ||
           strstr(value, "tutorial") || strstr(value, "Tutorial") || strstr(value, "TUTORIAL") ||
           strstr(value, "version") || strstr(value, "Version") || strstr(value, "VERSION");
}

static void log_db_read(const char *kind, const void *key1, const void *key2, int result) {
    char first[4097];
    char second[4097];
    int first_ok = read_game_string(key1, first, sizeof(first));
    int second_ok = key2 && read_game_string(key2, second, sizeof(second));

    /* Keep normal UI/resource reads quiet, but always retain failed reads. */
    if (result != 0 && !(first_ok && relevant_db_key(first)) && !(second_ok && relevant_db_key(second))) return;
    __android_log_print(ANDROID_LOG_WARN, "BLUSTONE_DB_TRACE",
        "%s result=%d key1=%s key2=%s", kind, result,
        first_ok ? first : "<unreadable>", second_ok ? second : "<none>");
}

typedef int (*JsonGetFunction)(void *self, const void *key, void *json);
typedef int (*StringGetFunction)(void *self, const void *key1, const void *key2, void *value);
static JsonGetFunction original_json_get;
static StringGetFunction original_string_get;
static StringGetFunction original_string_get_template;
static volatile sig_atomic_t db_hooks_installed;

/* The shipped stage transition occasionally calls one of several exported
 * LoadAnim2 overloads with a null/empty resource name. The native failure
 * path logs the missing name and then dereferences a null animation node.
 * Keep valid resource lookups untouched; only substitute a known loaded
 * button animation for the empty-name case. */
typedef void *(*ResourceLoadAnim2Function)(void *self, const char *name);
typedef void *(*ObjectLoadAnim2Function)(void *self, const char *name, char arg2, unsigned char arg3);
typedef void *(*ResourceMakeAnim2FromVideoFunction)(void *self, const char *name, unsigned int flags);
static ResourceLoadAnim2Function original_resource_mgr_load_anim2;
static ResourceLoadAnim2Function original_ui_base_load_anim2;
static ObjectLoadAnim2Function original_csr_obj_load_anim2;
static ResourceMakeAnim2FromVideoFunction original_make_anim2_from_video;
static volatile sig_atomic_t resource_guard_thread_started;
static volatile sig_atomic_t resource_guard_thread_running;

/* CDN/bootstrap probes. These offsets are for the shipped libnative_core.so
 * that was analyzed in analysis/native-datamgr-callers.txt. They are only
 * installed in the diagnostic APK and are deliberately observational. */
typedef uint64_t (*CdnGetResVerFunction)(void *self);
typedef uint64_t (*CdnGetResVerDirFunction)(void *self, const void *name, int directory);
typedef void (*CdnParseHeaderFunction)(void *self, const void *bytes);
typedef void (*DataMgrInitFunction)(void *self);
typedef void (*DataMgrParseLauncherFunction)(void *self, int result, const void *json);
typedef void (*SceneRequestLaunchFunction)(void *self);
static CdnGetResVerFunction original_cdn_get_res_ver;
static CdnGetResVerDirFunction original_cdn_get_res_ver_dir;
static CdnParseHeaderFunction original_cdn_parse_header;
static DataMgrInitFunction original_data_mgr_init;
static DataMgrParseLauncherFunction original_data_mgr_parse_launcher;
static SceneRequestLaunchFunction original_scene_request_launch;

static void install_db_hooks(void *game);

static void try_install_db_hooks(void *game) {
    /* Houdini translates libnative_core.so before these callbacks run.  An
     * inline rewrite of the already-translated Thumb entry points is not a
     * safe observation mechanism: it can jump through stale translated code
     * and take the game down before any key is logged.  Keep the experimental
     * hook implementation in the source for native/emulator work, but leave
     * it opt-in until a cache-safe instrumentation path is available. */
    (void)game;
    db_hooks_installed = 1;
    __android_log_print(ANDROID_LOG_INFO, "BLUSTONE_DB_TRACE",
        "LevelDB inline hooks disabled on Houdini; signal tracing remains active");
    return;
#if 0
    if (game && !db_hooks_installed) {
        install_db_hooks(game);
        db_hooks_installed = 1;
    }
#endif
}

static uint64_t hooked_cdn_get_res_ver(void *self) {
    uint64_t result = original_cdn_get_res_ver ? original_cdn_get_res_ver(self) : 0;
    __android_log_print(ANDROID_LOG_INFO, "BLUSTONE_CDN_TRACE",
        "GetResVer result=%llu", (unsigned long long)result);
    return result;
}

static uint64_t hooked_cdn_get_res_ver_dir(void *self, const void *name, int directory) {
    uint64_t result = original_cdn_get_res_ver_dir ?
        original_cdn_get_res_ver_dir(self, name, directory) : 0;
    char text[1025];
    int readable = read_game_string(name, text, sizeof(text));
    __android_log_print(ANDROID_LOG_INFO, "BLUSTONE_CDN_TRACE",
        "GetResVerDir result=%llu directory=%d name=%s",
        (unsigned long long)result, directory, readable ? text : "<unreadable>");
    return result;
}

static void hooked_cdn_parse_header(void *self, const void *bytes) {
    __android_log_print(ANDROID_LOG_INFO, "BLUSTONE_CDN_TRACE",
        "ParseHeader self=%p bytes=%p", self, bytes);
    if (original_cdn_parse_header) original_cdn_parse_header(self, bytes);
}

static void hooked_data_mgr_init(void *self) {
    __android_log_print(ANDROID_LOG_INFO, "BLUSTONE_CDN_TRACE", "DataMgr::Init self=%p", self);
    if (original_data_mgr_init) original_data_mgr_init(self);
}

static void hooked_data_mgr_parse_launcher(void *self, int result, const void *json) {
    __android_log_print(ANDROID_LOG_INFO, "BLUSTONE_CDN_TRACE",
        "DataMgr::ParseLauncherResp result=%d json=%p", result, json);
    if (original_data_mgr_parse_launcher) original_data_mgr_parse_launcher(self, result, json);
}

static void hooked_scene_request_launch(void *self) {
    __android_log_print(ANDROID_LOG_INFO, "BLUSTONE_CDN_TRACE",
        "SceneCI::RequestLaunch self=%p", self);
    if (original_scene_request_launch) original_scene_request_launch(self);
}

static int hooked_json_get(void *self, const void *key, void *json) {
    int result = original_json_get ? original_json_get(self, key, json) : 0;
    log_db_read("json_get", key, 0, result);
    return result;
}

static int hooked_string_get(void *self, const void *key1, const void *key2, void *value) {
    int result = original_string_get ? original_string_get(self, key1, key2, value) : 0;
    log_db_read("string_get", key1, key2, result);
    return result;
}

static int hooked_string_get_template(void *self, const void *key1, const void *key2, void *value) {
    int result = original_string_get_template ? original_string_get_template(self, key1, key2, value) : 0;
    log_db_read("string_get_template", key1, key2, result);
    return result;
}

/* A Thumb-2 absolute jump: ldr.w pc, [pc, #0]; .word destination|1. */
static int install_inline_hook(void *target, void *replacement, void **trampoline_out) {
    const size_t stolen = 8;
    long page_size = sysconf(_SC_PAGESIZE);
    uintptr_t address = (uintptr_t)target & ~(uintptr_t)1;
    uintptr_t page;
    uint32_t jump = 0xf000f8dfU;
    uint32_t destination;
    void *trampoline;

    if (!target || !replacement || !trampoline_out || page_size <= 0) return 0;
    page = address & ~((uintptr_t)page_size - 1U);
    trampoline = mmap(0, (size_t)page_size, PROT_READ | PROT_WRITE,
                      MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (trampoline == MAP_FAILED) return 0;

    memcpy(trampoline, (const void *)address, stolen);
    memcpy((uint8_t *)trampoline + stolen, &jump, sizeof(jump));
    destination = (uint32_t)(address + stolen) | 1U;
    memcpy((uint8_t *)trampoline + stolen + sizeof(jump), &destination, sizeof(destination));
    if (mprotect(trampoline, (size_t)page_size, PROT_READ | PROT_EXEC) != 0) return 0;

    if (mprotect((void *)page, (size_t)page_size, PROT_READ | PROT_WRITE | PROT_EXEC) != 0) return 0;
    destination = (uint32_t)(uintptr_t)replacement | 1U;
    memcpy((void *)address, &jump, sizeof(jump));
    memcpy((uint8_t *)address + sizeof(jump), &destination, sizeof(destination));
    __builtin___clear_cache((char *)address, (char *)(address + stolen));
    (void)mprotect((void *)page, (size_t)page_size, PROT_READ | PROT_EXEC);

    *trampoline_out = (void *)((uintptr_t)trampoline | 1U);
    return 1;
}

static const char *guarded_anim_name(const char *symbol, const char *name) {
    if (!name || name[0] == '\0') {
        __android_log_print(ANDROID_LOG_WARN, "BLUSTONE_RESOURCE_GUARD",
            "substituting %s LoadAnim2 name (%s) with UI_BT_PRE_S",
            symbol, name ? "empty" : "null");
        return "UI_BT_PRE_S";
    }
    return name;
}

static void *hooked_resource_mgr_load_anim2(void *self, const char *name) {
    const char *safe_name = guarded_anim_name("CRMResourceMgr", name);
    __android_log_print(ANDROID_LOG_WARN, "BLUSTONE_RESOURCE_GUARD",
        "CRMResourceMgr LoadAnim2 name=%s", safe_name);
    if (name && strcmp(name, "UI_MA_L1") == 0) {
        __android_log_print(ANDROID_LOG_WARN, "BLUSTONE_RESOURCE_GUARD",
            "skipping unsupported video animation UI_MA_L1");
        return 0;
    }
    return original_resource_mgr_load_anim2 ?
        original_resource_mgr_load_anim2(self, safe_name) : 0;
}

static void *hooked_ui_base_load_anim2(void *self, const char *name) {
    const char *safe_name = guarded_anim_name("CMUIBase", name);
    return original_ui_base_load_anim2 ?
        original_ui_base_load_anim2(self, safe_name) : 0;
}

static void *hooked_csr_obj_load_anim2(void *self, const char *name, char arg2, unsigned char arg3) {
    const char *safe_name = guarded_anim_name("CSRObj", name);
    return original_csr_obj_load_anim2 ?
        original_csr_obj_load_anim2(self, safe_name, arg2, arg3) : 0;
}

static void *hooked_make_anim2_from_video(void *self, const char *name, unsigned int flags) {
    const char *safe_name = guarded_anim_name("MakeAnim2FromVideo", name);
    __android_log_print(ANDROID_LOG_WARN, "BLUSTONE_RESOURCE_GUARD",
        "MakeAnim2FromVideo name=%s flags=%u", safe_name, flags);
    if (name && strcmp(name, "UI_MA_L1") == 0) {
        __android_log_print(ANDROID_LOG_WARN, "BLUSTONE_RESOURCE_GUARD",
            "returning empty animation for unsupported video UI_MA_L1");
        return 0;
    }
    return original_make_anim2_from_video ?
        original_make_anim2_from_video(self, safe_name, flags) : 0;
}

static int install_one_resource_guard(void *game, const char *label,
        const char *mangled_name, void *replacement, void **original) {
    void *target = game ? dlsym(game, mangled_name) : 0;
    uintptr_t address = (uintptr_t)target & ~(uintptr_t)1;
    uint32_t jump;
    uint32_t destination;

    if (target) {
        memcpy(&jump, (const void *)address, sizeof(jump));
        memcpy(&destination, (const uint8_t *)address + sizeof(jump), sizeof(destination));
        if (jump == 0xf000f8dfU &&
            ((uintptr_t)destination & ~(uintptr_t)1) == ((uintptr_t)replacement & ~(uintptr_t)1)) {
            return 0;
        }
    }
    if (!target || !install_inline_hook(target, replacement, original)) {
        __android_log_print(ANDROID_LOG_ERROR, "BLUSTONE_RESOURCE_GUARD",
            "%s LoadAnim2 guard was not installed target=%p errno=%d",
            label, target, errno);
        return 0;
    }
    __android_log_print(ANDROID_LOG_INFO, "BLUSTONE_RESOURCE_GUARD",
        "%s LoadAnim2 guard installed target=%p", label, target);
    return 1;
}

static void install_resource_guard(void *game) {
    static const char *resource_mgr_name = "_ZN15CRMResourceMgr49LoadAnim2EPKc";
    static const char *ui_base_name = "_ZN8CMUIBase9LoadAnim2EPKc";
    static const char *csr_obj_name = "_ZN6CSRObj9LoadAnim2EPKchh";
    static const char *make_anim2_from_video_name = "_ZN15CRMResourceMgr418MakeAnim2FromVideoEPKcj";
    int hooks = 0;

    hooks += install_one_resource_guard(game, "CRMResourceMgr", resource_mgr_name,
        (void *)hooked_resource_mgr_load_anim2,
        (void **)&original_resource_mgr_load_anim2);
    hooks += install_one_resource_guard(game, "CMUIBase", ui_base_name,
        (void *)hooked_ui_base_load_anim2,
        (void **)&original_ui_base_load_anim2);
    hooks += install_one_resource_guard(game, "CSRObj", csr_obj_name,
        (void *)hooked_csr_obj_load_anim2,
        (void **)&original_csr_obj_load_anim2);
    hooks += install_one_resource_guard(game, "MakeAnim2FromVideo", make_anim2_from_video_name,
        (void *)hooked_make_anim2_from_video,
        (void **)&original_make_anim2_from_video);
    if (hooks > 0) {
        __android_log_print(ANDROID_LOG_INFO, "BLUSTONE_RESOURCE_GUARD",
            "LoadAnim2 guards installed=%d", hooks);
    }
}

static void *resource_guard_worker(void *opaque) {
    (void)opaque;
    while (resource_guard_thread_running) {
        void *game = dlopen("libnative_core.so", RTLD_NOW);
        if (game) install_resource_guard(game);
        sleep(1);
    }
    return 0;
}

static void install_db_hooks(void *game) {
    static const char *json_name =
        "_ZNK10CGMLevelDB3GetERKNSt6__ndk112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEERN8nlohmann10basic_jsonINS0_3mapENS0_6vectorES6_bxydS4_NS9_14adl_serializerENSC_IhNS4_IhEEEEEE";
    static const char *string_name =
        "_ZNK10CGMLevelDB3GetERKNSt6__ndk112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEES8_RS6_";
    static const char *template_name =
        "_ZNK10CGMLevelDB3GetINSt6__ndk112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEEEEKhRKS7_SA_RT_";
    void *json = dlsym(game, json_name);
    void *string = dlsym(game, string_name);
    void *string_template = dlsym(game, template_name);
    int hooks = 0;

    if (json && install_inline_hook(json, (void *)hooked_json_get, (void **)&original_json_get)) hooks++;
    if (string && install_inline_hook(string, (void *)hooked_string_get, (void **)&original_string_get)) hooks++;
    if (string_template && install_inline_hook(string_template, (void *)hooked_string_get_template, (void **)&original_string_get_template)) hooks++;
    __android_log_print(ANDROID_LOG_INFO, "BLUSTONE_DB_TRACE",
        "LevelDB hooks installed=%d json=%p string=%p template=%p errno=%d",
        hooks, json, string, string_template, errno);
}

static void install_cdn_hooks(void) {
    const uintptr_t offsets[] = {
        0x7cf584U, /* CPVCDN::GetResVer() */
        0x7cf230U, /* CPVCDN::GetResVer(string, RMF_DIR) */
        0x7d22ecU, /* CPVCDN::ParseHeader(vector) */
        0x7e0b60U, /* CPVDataMgr::Init() */
        0x7e12c4U, /* CPVDataMgr::ParseLauncherResp(int, json) */
        0x00e06098U /* CSRSceneCI::RequestLaunch() */
    };
    int hooks = 0;
    if (!game_start) {
        __android_log_print(ANDROID_LOG_ERROR, "BLUSTONE_CDN_TRACE",
            "CDN hooks skipped: game base is unavailable");
        return;
    }
    if (install_inline_hook((void *)(game_start + offsets[0] + 1U),
            (void *)hooked_cdn_get_res_ver, (void **)&original_cdn_get_res_ver)) hooks++;
    if (install_inline_hook((void *)(game_start + offsets[1] + 1U),
            (void *)hooked_cdn_get_res_ver_dir, (void **)&original_cdn_get_res_ver_dir)) hooks++;
    if (install_inline_hook((void *)(game_start + offsets[2] + 1U),
            (void *)hooked_cdn_parse_header, (void **)&original_cdn_parse_header)) hooks++;
    /* DataMgr/scene hooks are intentionally disabled: their callers use
     * engine-specific ABI details and are too invasive for early startup. */
    __android_log_print(ANDROID_LOG_INFO, "BLUSTONE_CDN_TRACE",
        "bootstrap hooks installed=%d base=%p", hooks, (void *)game_start);
}

static void address(const char *kind, uintptr_t pc) {
    Dl_info info = {0};
    if (dladdr((void *)pc, &info) && info.dli_fbase) {
        __android_log_print(ANDROID_LOG_ERROR, "BLUSTONE_ARM", "%s pc=%p module=%s offset=0x%lx symbol=%s",
            kind, (void *)pc, info.dli_fname, (unsigned long)(pc - (uintptr_t)info.dli_fbase),
            info.dli_sname ? info.dli_sname : "?");
    } else {
        __android_log_print(ANDROID_LOG_ERROR, "BLUSTONE_ARM", "%s pc=%p (unresolved)", kind, (void *)pc);
    }
}

static _Unwind_Reason_Code frame(struct _Unwind_Context *context, void *counter) {
    unsigned *count = counter;
    if ((*count)++ >= 20) return _URC_END_OF_STACK;
    address("frame", _Unwind_GetIP(context));
    return _URC_NO_REASON;
}

static void fault(int signal_number, siginfo_t *signal_info, void *opaque) {
    ucontext_t *context = opaque;
    __android_log_print(ANDROID_LOG_ERROR, "BLUSTONE_ARM", "signal=%d code=%d fault=%p",
        signal_number, signal_info->si_code, signal_info->si_addr);
#if defined(__arm__)
    address("ARM-PC", context->uc_mcontext.arm_pc);
    address("ARM-LR", context->uc_mcontext.arm_lr);
    __android_log_print(ANDROID_LOG_ERROR, "BLUSTONE_ARM", "sp=%08lx fp=%08lx r0=%08lx r1=%08lx r2=%08lx r3=%08lx",
        context->uc_mcontext.arm_sp, context->uc_mcontext.arm_fp,
        context->uc_mcontext.arm_r0, context->uc_mcontext.arm_r1,
        context->uc_mcontext.arm_r2, context->uc_mcontext.arm_r3);
    {
        const unsigned char *text = (const unsigned char *)(uintptr_t)context->uc_mcontext.arm_r1;
        char preview[65];
        unsigned i;
        for (i = 0; i < sizeof(preview) - 1; i++) {
            unsigned char ch = text[i];
            if (!ch) break;
            preview[i] = (ch >= 0x20 && ch <= 0x7e) ? (char)ch : '.';
        }
        preview[i] = '\0';
        __android_log_print(ANDROID_LOG_ERROR, "BLUSTONE_ARM",
            "r1-preview=%s", preview);
    }
    /* Candidate return addresses, not an unwound backtrace. Keep the scan
     * within the current 4 KiB stack page to avoid crossing an unmapped page. */
    uintptr_t sp = context->uc_mcontext.arm_sp;
    unsigned words = (4096 - (sp & 4095)) / sizeof(uintptr_t);
    if (words > 256) words = 256;
    for (unsigned i = 0; i < words; i++) {
        uintptr_t candidate = ((uintptr_t *)sp)[i];
        if (candidate >= game_start && candidate < game_end) {
            __android_log_print(ANDROID_LOG_ERROR, "BLUSTONE_ARM", "stack-candidate word=%u", i);
            address("candidate", candidate);
        }
    }
#endif
    unsigned count = 0;
    _Unwind_Backtrace(frame, &count);
    /* Terminate after recording, never resume a faulting game instruction. */
    _exit(128 + signal_number);
}

JNIEXPORT void JNICALL Java_com_vshower_sr_MainActivity_enableCrashTrace(JNIEnv *env, jclass klass) {
    (void)env; (void)klass;
    if (installed) {
        try_install_db_hooks(dlopen("libnative_core.so", RTLD_NOW));
        return;
    }
    /* Houdini's dl_iterate_phdr bridge crashes here. dladdr/dlsym are already
     * verified in this emulator. Bound only candidate filtering, never reads. */
    void *game = dlopen("libnative_core.so", RTLD_NOW);
    Dl_info info = {0};
    void *known = game ? dlsym(game, "_ZN10CSRRefData12FindCardBookE9CHAR_ROLEj") : 0;
    if (known && dladdr(known, &info)) {
        game_start = (uintptr_t)info.dli_fbase;
        game_end = game_start + 0x2200000;
    }
    struct sigaction action = {0};
    action.sa_sigaction = fault;
    action.sa_flags = SA_SIGINFO | SA_RESETHAND;
    sigemptyset(&action.sa_mask);
    const int signals[] = { SIGSEGV, SIGBUS, SIGABRT, SIGILL, SIGFPE };
    for (unsigned i = 0; i < sizeof(signals) / sizeof(signals[0]); i++)
        sigaction(signals[i], &action, 0);
    if (!game) {
        __android_log_print(ANDROID_LOG_ERROR, "BLUSTONE_DB_TRACE", "libnative_core.so was not available for DB hooks");
    } else {
        /* These hooks only observe recovered LevelDB keys and return values.
         * Keep animation/resource hooks disabled because Houdini does not
         * reliably invalidate translated Thumb code after inline rewrites. */
        try_install_db_hooks(game);
    }
    installed = 1;
    __android_log_print(ANDROID_LOG_INFO, "BLUSTONE_ARM", "ARM crash probe installed (signal handlers only)");
}

JNIEXPORT void JNICALL Java_com_vshower_sr_MainActivity_enableResourceGuard(JNIEnv *env, jclass klass) {
    (void)env;
    (void)klass;
    /* The instrumented APK now carries a static, instrumented-only patch for
     * MakeAnim2FromVideo.  Houdini does not reliably invalidate translated
     * Thumb code after an inline rewrite, so leave the native code untouched
     * at runtime and keep this entry point as an explicit diagnostic marker. */
    __android_log_print(ANDROID_LOG_INFO, "BLUSTONE_RESOURCE_GUARD",
        "static UI_MA_L1 fallback active; runtime inline hooks disabled");
    return;
#if 0
    void *game = dlopen("libnative_core.so", RTLD_NOW);
    if (game) install_resource_guard(game);
    if (!resource_guard_thread_started) {
        pthread_t thread;
        resource_guard_thread_started = 1;
        resource_guard_thread_running = 1;
        if (pthread_create(&thread, 0, resource_guard_worker, 0) == 0) {
            pthread_detach(thread);
        } else {
            resource_guard_thread_running = 0;
            __android_log_print(ANDROID_LOG_ERROR, "BLUSTONE_RESOURCE_GUARD",
                "failed to start refresh worker");
        }
    }
    if (!game) {
        __android_log_print(ANDROID_LOG_ERROR, "BLUSTONE_RESOURCE_GUARD",
            "libnative_core.so was not available for LoadAnim2 guard");
    }
#endif
}
