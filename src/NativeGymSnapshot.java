package com.vshower.instrumented;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.io.RandomAccessFile;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/** Version28010, instrumented-only, bounded READS of this process. No debugger,
 * native calls, memory writes, marker changes, game actions or account fields.
 * Offsets/proven vptrs: analysis/research/gym-selected-source-reader.md. */
final class NativeGymSnapshot {
    private static final long APP_VPTR = 0x2140cb0L, MANAGER_VPTR = 0x21735a4L;
    private static final long TUTORIAL_VPTR = 0x2176e20L, ORDINARY_VPTR = 0x218278cL;
    private static final long MAX_ID = 9007199254740991L;
    private static final long PARTNER_VPTR = 0x216f2ecL;
    private static final long GUIDE_VPTR = 0x21691d4L, FOCUS_VPTR = 0x2185f4cL;
    private static final class Region {
        final long start, end; final boolean readable;
        Region(long start, long end, boolean readable) { this.start=start; this.end=end; this.readable=readable; }
    }
    private static final class Memory implements AutoCloseable {
        final List<Region> regions = new ArrayList<>();
        final RandomAccessFile file;
        long base;
        Memory() throws Exception {
            int bytes=0, lines=0;
            try (BufferedReader maps = new BufferedReader(new InputStreamReader(
                    new FileInputStream("/proc/self/maps"), StandardCharsets.US_ASCII))) {
                String line;
                while ((line=maps.readLine())!=null) {
                    bytes+=line.length()+1;
                    if (++lines>8192 || bytes>1048576) throw new IllegalStateException("maps_bound");
                    String[] parts=line.trim().split("\\s+",6), range=parts[0].split("-");
                    if (parts.length<3 || range.length!=2) throw new IllegalStateException("maps_format");
                    long start=Long.parseLong(range[0],16),end=Long.parseLong(range[1],16);
                    regions.add(new Region(start,end,parts[1].startsWith("r")));
                    if (parts.length==6 && parts[5].endsWith("/libnative_core.so") && Long.parseLong(parts[2],16)==0) {
                        if (base!=0 && base!=start) throw new IllegalStateException("ambiguous_library");
                        base=start;
                    }
                }
            }
            if (base==0) throw new IllegalStateException("native_not_loaded");
            file=new RandomAccessFile("/proc/self/mem","r");
        }
        byte[] read(long address,int count) throws Exception {
            if (address<4096 || count<1 || count>4096 || address+count<address) throw new IllegalStateException("read_bound");
            boolean mapped=false;
            for (Region r:regions) if(r.readable && address>=r.start && address+count<=r.end) { mapped=true;break; }
            if (!mapped) throw new IllegalStateException("unmapped");
            byte[] bytes=new byte[count]; file.seek(address); file.readFully(bytes); return bytes;
        }
        long u32(long address) throws Exception { return ByteBuffer.wrap(read(address,4)).order(ByteOrder.LITTLE_ENDIAN).getInt()&0xffffffffL; }
        long u64(long address) throws Exception {
            long value=ByteBuffer.wrap(read(address,8)).order(ByteOrder.LITTLE_ENDIAN).getLong();
            if (value<0 || value>MAX_ID) throw new IllegalStateException("id_bound"); return value;
        }
        long[] header(long address) throws Exception { return new long[]{u32(address),u32(address+4),u32(address+8)}; }
        long[] ids(long[] h) throws Exception {
            long begin=h[0],end=h[1],capacity=h[2];
            if ((begin&7)!=0 || begin>end || end>capacity || (end-begin)%8!=0 || (end-begin)/8>32 ||
                (begin==0 && (end!=0 || capacity!=0))) throw new IllegalStateException("vector_bound");
            long[] ids=new long[(int)((end-begin)/8)];
            for(int i=0;i<ids.length;i++) ids[i]=u64(begin+i*8); return ids;
        }
        public void close() throws Exception { file.close(); }
    }
    private static boolean sameOwner(Memory m,long app,long manager,long scene,long control,long vptr) throws Exception {
        return m.u32(m.base+0x21ef1e0L)==app && m.u32(app)==m.base+APP_VPTR && m.u32(app+8)==manager &&
            m.u32(manager)==m.base+MANAGER_VPTR && m.u32(manager+0x34)==scene && m.u32(manager+0x38)==control &&
            (int)m.u32(control+4)>=0 && m.u32(scene)==vptr;
    }
    static JSONObject capture(Context context) {
        JSONObject result=new JSONObject();
        try {
            if (!"com.vshower.prd_sr.instrumented".equals(context.getPackageName()) ||
                context.getPackageManager().getPackageInfo(context.getPackageName(),0).versionCode!=28010) {
                result.put("status","wrong_package_or_version"); return result;
            }
            try (Memory m=new Memory()) {
                long app=m.u32(m.base+0x21ef1e0L);
                if((app&3)!=0 || m.u32(app)!=m.base+APP_VPTR) throw new IllegalStateException("app_guard");
                long manager=m.u32(app+8);
                if (m.u32(manager)!=m.base+MANAGER_VPTR) throw new IllegalStateException("manager_guard");
                long scene=m.u32(manager+0x34),control=m.u32(manager+0x38),vptr=m.u32(scene);
                if (control==0 || (int)m.u32(control+4)<0) throw new IllegalStateException("expired_scene");
                if(vptr!=m.base+TUTORIAL_VPTR && vptr!=m.base+ORDINARY_VPTR) {
                    if (!sameOwner(m,app,manager,scene,control,vptr))
                        throw new IllegalStateException("unstable");
                    result.put("status","unsupported_scene");
                    long relative=vptr-m.base;
                    if(relative>0 && relative<0x3000000L) result.put("elf_vptr","0x"+Long.toHexString(relative));
                    return result;
                }
                long target=m.u64(scene+0xd48);
                long[] candidatesHeader=m.header(scene+0x65c),selectedHeader=m.header(scene+0x668);
                long[] candidates=m.ids(candidatesHeader),selected=m.ids(selectedHeader);
                // No suspension: headers AND content are reread, with exact
                // current-scene ownership/target checks. Observed changes are
                // discarded; this cannot exclude ABA reuse or freeze the UI.
                if(!sameOwner(m,app,manager,scene,control,vptr) || m.u64(scene+0xd48)!=target ||
                   !Arrays.equals(candidatesHeader,m.header(scene+0x65c)) || !Arrays.equals(selectedHeader,m.header(scene+0x668)) ||
                   !Arrays.equals(candidates,m.ids(candidatesHeader)) || !Arrays.equals(selected,m.ids(selectedHeader)))
                    throw new IllegalStateException("unstable");
                if(!sameOwner(m,app,manager,scene,control,vptr) || m.u64(scene+0xd48)!=target ||
                   !Arrays.equals(candidatesHeader,m.header(scene+0x65c)) || !Arrays.equals(selectedHeader,m.header(scene+0x668)))
                    throw new IllegalStateException("unstable");
                result.put("status","stable");
                result.put("scene",vptr==m.base+TUTORIAL_VPTR ? "TutorialLevelUp" : "TableLevelUp");
                result.put("target",target);
                JSONArray c=new JSONArray(),s=new JSONArray();
                for(long id:candidates)c.put(id); for(long id:selected)s.put(id);
                result.put("candidates",c); result.put("selected",s);
            }
        } catch (Exception unavailable) {
            // Never dump memory/paths/exception text or scan for a substitute.
            try { result=new JSONObject(); result.put("status","unavailable"); } catch(Exception ignored) {}
        }
        return result;
    }

    /** Search diagnostics reuse the guarded reader; no names, account fields,
     * native calls or writes. The scene-owned guide is not necessarily the top
     * modal. Layout evidence: search-partner-navigation-block.md. */
    static JSONObject captureSearch(Context context) {
        JSONObject result = new JSONObject();
        try {
            if (!"com.vshower.prd_sr.instrumented".equals(context.getPackageName()) ||
                context.getPackageManager().getPackageInfo(context.getPackageName(),0).versionCode != 28010) {
                result.put("status", "wrong_package_or_version"); return result;
            }
            try (Memory m = new Memory()) {
                long app = m.u32(m.base + 0x21ef1e0L);
                if ((app & 3) != 0 || m.u32(app) != m.base + APP_VPTR) throw new IllegalStateException("app_guard");
                long manager = m.u32(app + 8);
                if (m.u32(manager) != m.base + MANAGER_VPTR) throw new IllegalStateException("manager_guard");
                long scene = m.u32(manager + 0x34), control = m.u32(manager + 0x38), vptr = m.u32(scene);
                if (control == 0 || (int)m.u32(control + 4) < 0) throw new IllegalStateException("expired_scene");
                if (vptr != m.base + PARTNER_VPTR) {
                    if (!sameOwner(m,app,manager,scene,control,vptr)) throw new IllegalStateException("unstable");
                    result.put("status", "unsupported_scene"); return result;
                }
                SearchObservation observed = searchFields(m, scene);
                SearchObservation repeated = searchFields(m, scene);
                if (!sameOwner(m,app,manager,scene,control,vptr) ||
                    !observed.json.toString().equals(repeated.json.toString()) ||
                    !observed.anchors.equals(repeated.anchors) ||
                    !sameOwner(m,app,manager,scene,control,vptr)) throw new IllegalStateException("unstable");
                observed.json.put("status", "stable"); observed.json.put("scene", "FindShardSelSupporter");
                return observed.json;
            }
        } catch (Exception unavailable) {
            try { result = new JSONObject(); result.put("status", "unavailable"); } catch (Exception ignored) {}
        }
        return result;
    }

    private static int vectorCount(long[] h, int stride, int limit) {
        // Only the proven begin/end fields are used here; capacity is not read.
        if (h.length != 2 || (h[0] & 3) != 0 || h[0] > h[1] || (h[1]-h[0]) % stride != 0 ||
            (h[1]-h[0])/stride > limit || (h[0] == 0 && h[1] != 0))
            throw new IllegalStateException("vector_bound");
        return (int)((h[1]-h[0])/stride);
    }

    private static long[] pair(Memory m, long address) throws Exception {
        return new long[]{m.u32(address), m.u32(address+4)};
    }

    private static final class SearchObservation {
        final JSONObject json = new JSONObject();
        // Pointer/header identity is compared internally and never emitted.
        final List<Long> anchors = new ArrayList<>();
        void anchor(long... values) { for (long value:values) anchors.add(value); }
    }

    private static SearchObservation searchFields(Memory m, long scene) throws Exception {
        SearchObservation observation = new SearchObservation();
        JSONObject result = observation.json;
        long[] groups = pair(m, scene + 0x678);
        observation.anchor(groups);
        int groupCount = vectorCount(groups, 0x1c, 8), eligible = 0;
        JSONArray rows = new JSONArray();
        for (int i=0; i<groupCount; i++) {
            long group = groups[0] + i*0x1c;
            long type = m.u32(group);
            if (type > 3) throw new IllegalStateException("group_type");
            long[] thumbs = pair(m, group + 0x10);
            observation.anchor(thumbs);
            int count = vectorCount(thumbs, 0x38, 32);
            JSONObject summary = new JSONObject(); summary.put("type", type); summary.put("count", count);
            if (type == 2) {
                JSONArray available = new JSONArray();
                for (int j=0; j<count; j++) {
                    int flag = m.read(thumbs[0] + j*0x38 + 0x28, 1)[0] & 255;
                    if (flag > 1) throw new IllegalStateException("availability_flag");
                    available.put(flag); if (flag == 1) eligible++;
                }
                summary.put("availability", available);
            }
            if (!Arrays.equals(thumbs, pair(m, group + 0x10))) throw new IllegalStateException("unstable");
            rows.put(summary);
        }
        if (!Arrays.equals(groups, pair(m, scene + 0x678))) throw new IllegalStateException("unstable");
        result.put("groups", rows); result.put("eligible_virtual_helpers", eligible);
        int input = m.read(scene + 0x2c, 1)[0] & 255;
        if (input > 1) throw new IllegalStateException("input_flag");
        // +2c gates generic SceneBack; it is not renderer activation (+39)
        // and does not gate the direct OnProcessHomeKey handler.
        result.put("scene_back_enabled", input == 1);
        long guide = m.u32(scene + 0x6ac), guideControl = m.u32(scene + 0x6b0);
        observation.anchor(guide, guideControl);
        result.put("scene_guide_present", guide != 0);
        if (guide != 0) {
            if (guideControl == 0 || (int)m.u32(guideControl+4) < 0 || m.u32(guide) != m.base+GUIDE_VPTR)
                throw new IllegalStateException("guide_guard");
            long focus = m.u32(guide+0xc4), focusControl = m.u32(guide+0xc8);
            observation.anchor(focus, focusControl);
            result.put("scene_guide_focus_present", focus != 0);
            if (focus != 0) {
                if (focusControl == 0 || (int)m.u32(focusControl+4) < 0 || m.u32(focus) != m.base+FOCUS_VPTR)
                    throw new IllegalStateException("focus_guard");
                long active = m.u32(focus+0x850);
                observation.anchor(active);
                result.put("scene_guide_focus_active", active != 0);
                if (m.u32(focus+0x850) != active || m.u32(focus) != m.base+FOCUS_VPTR ||
                    (int)m.u32(focusControl+4) < 0) throw new IllegalStateException("unstable");
            } else if (focusControl != 0) throw new IllegalStateException("focus_pair");
            if (m.u32(guide+0xc4) != focus || m.u32(guide+0xc8) != focusControl ||
                m.u32(guide) != m.base+GUIDE_VPTR || (int)m.u32(guideControl+4) < 0)
                throw new IllegalStateException("unstable");
        } else if (guideControl != 0) throw new IllegalStateException("guide_pair");
        if (m.u32(scene+0x6ac) != guide || m.u32(scene+0x6b0) != guideControl)
            throw new IllegalStateException("unstable");
        return observation;
    }
}
