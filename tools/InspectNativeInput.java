import com.sun.jdi.*;
import com.sun.jdi.connect.*;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Read-only, bounded in-process guest state through the instrumented APK's
 * existing JDWP connection. No game-native calls/hooks/patches; never target original
 * app. Exact version28010 pointers documented in native-live-state-reader.md.
 * Compile with tools/NativeCampaignMarkers.java and tools/NativeBattleControls.java
 * alongside this source.
 * Run after adb -s127.0.0.1:5555 forward tcp:8701 jdwp:<instrumentedPID>, then
 * tap once so Activity.dispatchTouchEvent supplies a suspended Java thread. */
public class InspectNativeInput {
  record Region(long start, long end, boolean readable) {}
  static VirtualMachine vm;
  static ThreadReference thread;
  static ClassType rafType;
  static ArrayType bytesType;
  static final Map<Integer,ArrayReference> readBuffers=new HashMap<>();
  static ObjectReference mem;
  static boolean cardsOnly;
  static boolean itemReferencesOnly;
  static boolean skillReferencesOnly;
  static boolean supplyOnly;
  static boolean combatTuningOnly;
  static boolean fuelUiOnly;
  static boolean villageUiOnly;
  static boolean gymSourcesOnly;
  static boolean guideStateOnly;
  static boolean resultUiOnly;
  static boolean campaignMarkersOnly;
  static boolean cdnCurrentOnly;
  static String cdnCopySpec;
  static boolean fishingHookOnly;
  static boolean episodeSceneOnly;
  static boolean episodeMaterialsOnly;
  static boolean episodeSkillsOnly;
  static boolean episodeExchangeOnly;
  static boolean rendererLayoutOnly;
  static boolean touchLayoutOnly;
  static boolean episodeBadgeOnly;
  static boolean episodeFeverOnly;
  static boolean episodeControlsOnly;
  static boolean arenaConfirmOnly;
  static boolean episodeTouchOnly;
  static int episodeTouchSkipEvents;
  static long episodeTouchSourceSerial;
  record HealSourceSelection(String ref,long serial) {
    HealSourceSelection {
      if(ref==null || !Set.of("C004","C049").contains(ref) || serial<=0 || serial>0xffffffffL)
        throw new IllegalArgumentException("Heal source requires C004/C049 and a positive low-word serial");
    }
  }
  static HealSourceSelection episodeHealSource;
  static boolean parseEpisodeFeverMode(String[] args) {
    boolean selected=args.length>1 && args[1].equals("--episode-fever");
    if(selected && (args.length!=3 || !args[2].equals("--frame")))
      throw new IllegalArgumentException("Episode fever requires only --frame");
    return selected;
  }
  static boolean parseEpisodeBadgeMode(String[] args) {
    boolean selected=args.length>1 && args[1].equals("--episode-badge");
    if(selected && !(args.length==3 && args[2].equals("--frame")) && parseHealSourceSelection(args)==null)
      throw new IllegalArgumentException("Episode badge requires --frame and optionally one exact heal-source pair");
    return selected;
  }
  static HealSourceSelection parseHealSourceSelection(String[] args) {
    String ref=null,serial=null;
    for(int i=0;i<args.length;i++) {
      String arg=args[i];
      if(!arg.startsWith("--heal-source"))continue;
      if(i<3 || args.length!=5 || !Set.of("--episode-skills","--episode-badge").contains(args[1]) || !args[2].equals("--frame"))
        throw new IllegalArgumentException("Heal source selection requires --episode-skills/--episode-badge --frame and exactly one ref/serial pair");
      if(arg.startsWith("--heal-source-ref=") && ref==null)ref=arg.substring("--heal-source-ref=".length());
      else if(arg.startsWith("--heal-source-serial=") && serial==null)serial=arg.substring("--heal-source-serial=".length());
      else throw new IllegalArgumentException("Unknown or duplicate heal source argument");
    }
    if(ref==null && serial==null)return null;
    if(ref==null || serial==null || !serial.matches("[1-9][0-9]{0,9}"))
      throw new IllegalArgumentException("Heal source requires one exact ref and positive decimal low-word serial");
    return new HealSourceSelection(ref,Long.parseLong(serial));
  }
  static long memoryReadCalls,memoryRequestedBytes,memoryReadNanos;
  static int[] observedLogicalDown;
  static List<Region> regions = new ArrayList<>();
  static void inspectArenaConfirm(long base) throws Exception {
    long app=u32(base+0x21ef1e0L),manager=u32(app+8);
    if(app==0 || manager==0 || u32(manager)!=base+0x21735a4L)
      throw new IllegalStateException("Arena confirmation scene manager unavailable");
    long scene=u32(manager+0x34),control=u32(manager+0x38);
    // make_shared Gec053c allocates7a8; scene occupies control+10/size798.
    if(scene==0 || control==0) throw new IllegalStateException("Arena confirmation current pair absent");
    long controlPrimary=u32(control);int ownerCount=(int)u32(control+4);
    boolean emplace=controlPrimary==base+0x2174a14L && scene==control+0x10;
    // shared_ptr constructor Gebffa4 stores raw scene at control+c;
    // Gec0074 consumes it through the scene's deleting destructor.
    boolean separate=controlPrimary==base+0x2174944L && u32(control+0xc)==scene;
    if(u32(scene)!=base+0x2171e34L || (!emplace && !separate) || ownerCount<0)
      throw new IllegalStateException(String.format("Current scene is not owned StageConfirm: primaryELF=%x controlPrimaryELF=%x objectMinusControl=%x; no confirmation reads",u32(scene)-base,u32(control)-base,scene-control));
    memory(scene,0x798);
    long sceneId=u32(scene+0x30);
    if(sceneId!=0x24) throw new IllegalStateException("StageConfirm is not Arena scene24");
    byte[] stageString=memory(scene+0x788,12);
    String stageId=cppString(scene+0x788,64);
    if(!stageId.matches("[A-Za-z0-9_]*")) throw new IllegalStateException("Unexpected bounded stage ID");
    // Exact GetStageData literal slots a280e8/e4 and ADDs a28012/a28004
    // resolve G21e2758/default INFO and G21e2804/guard (ELF offsets below).
    // Static provenance, not a guessed heap pointer; never initialize the guard.
    long fallback=base+0x21d2758L,guardAddress=base+0x21d2804L;
    int guard=memory(guardAddress,1)[0]&255;
    byte[] fallbackFields=(guard&1)!=0?memory(fallback,0xac):null;
    String fallbackDiagnostic="uninitialized_unread";
    if(fallbackFields!=null) fallbackDiagnostic=String.format("initialized_static_INFO apCost0=%d",Integer.toUnsignedLong(ByteBuffer.wrap(fallbackFields).order(ByteOrder.LITTLE_ENDIAN).getInt(0)));
    if(u32(base+0x21ef1e0L)!=app || u32(app+8)!=manager || u32(manager)!=base+0x21735a4L ||
       u32(manager+0x34)!=scene || u32(manager+0x38)!=control ||
       u32(scene)!=base+0x2171e34L || u32(control)!=controlPrimary || (int)u32(control+4)!=ownerCount ||
       (emplace ? scene!=control+0x10 : u32(control+0xc)!=scene) ||
       u32(scene+0x30)!=sceneId || !Arrays.equals(stageString,memory(scene+0x788,12)) ||
       !cppString(scene+0x788,64).equals(stageId) || (memory(guardAddress,1)[0]&255)!=guard ||
       (fallbackFields!=null && !Arrays.equals(fallbackFields,memory(fallback,0xac))))
      throw new IllegalStateException("Arena confirmation owner/fields changed; discard snapshot");
    System.out.printf("Arena confirmation diagnostic sceneELFvptr=2171e34 owner=%s sceneId30=%x stageId788=\"%s\" selectedStageINFO=unread feeBinding=unproved nativeGettersCalled=false%n",emplace?"emplace_verified":"separate_default_delete_verified",sceneId,stageId);
    System.out.printf("Stage default diagnostic ELFaddress=21d2758 guardELF=21d2804 guardByte=%x %s selectedByCurrentLookup=unproved%n",guard,fallbackDiagnostic);
  }
  static Method method(ReferenceType t, String n, String sig) {
    return t.methodsByName(n, sig).get(0);
  }
  static ObjectReference open(String path) throws Exception {
    ObjectReference file=rafType.newInstance(thread, method(rafType,"<init>","(Ljava/lang/String;Ljava/lang/String;)V"),
      List.of(vm.mirrorOf(path),vm.mirrorOf("r")), ObjectReference.INVOKE_SINGLE_THREADED);
    file.disableCollection();return file;
  }
  static byte[] read(ObjectReference file, int size) throws Exception {
    if(size<1 || size>4096) throw new IllegalArgumentException("bounded read only");
    ArrayReference buffer=readBuffers.get(size);
    if(buffer==null) {
      if(readBuffers.size()>=64)throw new IllegalStateException("read buffer size-count bound exceeded");
      for(int attempt=0;attempt<3 && buffer==null;attempt++) {
        ArrayReference candidate=bytesType.newInstance(size);
        try {candidate.disableCollection();buffer=candidate;}
        catch(ObjectCollectedException unpinned) { /* No file read occurred; retry allocation only. */ }
      }
      if(buffer==null)throw new IllegalStateException("unable to retain read buffer");
      readBuffers.put(size,buffer);
    }
    int count=((IntegerValue)file.invokeMethod(thread, method(rafType,"read","([B)I"),
      List.of(buffer),ObjectReference.INVOKE_SINGLE_THREADED)).value();
    if(count<0) return new byte[0];
    byte[] out=new byte[count];
    List<Value> values=buffer.getValues(0,count);
    for(int i=0;i<count;i++) out[i]=((ByteValue)values.get(i)).value();
    return out;
  }
  static void close(ObjectReference f) throws Exception {
    try { f.invokeMethod(thread,method(rafType,"close","()V"),List.of(),ObjectReference.INVOKE_SINGLE_THREADED); }
    finally { f.enableCollection(); }
  }
  static byte[] memory(long address, int size) throws Exception {
    if(address==0 || size<1 || size>4096 || regions.stream().noneMatch(r -> r.readable && address>=r.start && address+size<=r.end))
      throw new IllegalArgumentException("address outside readable mapping");
    long readStarted=System.nanoTime();memoryReadCalls++;memoryRequestedBytes+=size;
    try {
      mem.invokeMethod(thread,method(rafType,"seek","(J)V"),List.of(vm.mirrorOf(address)),ObjectReference.INVOKE_SINGLE_THREADED);
      byte[] out=read(mem,size);
      if(out.length!=size) throw new IllegalStateException("short memory read");
      return out;
    } finally { memoryReadNanos+=System.nanoTime()-readStarted; }
  }
  static long u32(long address) throws Exception {
    return Integer.toUnsignedLong(ByteBuffer.wrap(memory(address,4)).order(ByteOrder.LITTLE_ENDIAN).getInt());
  }
  static float f32(long address) throws Exception {
    return ByteBuffer.wrap(memory(address,4)).order(ByteOrder.LITTLE_ENDIAN).getFloat();
  }
  static ReferenceType uniqueType(String name) {
    List<ReferenceType> found=vm.classesByName(name);
    if(found.size()!=1) throw new IllegalStateException("Unique Java type unavailable: "+name);
    return found.get(0);
  }
  static Field exactField(ReferenceType type,String name,String signature,boolean isStatic) {
    Field field=type.fieldByName(name);
    if(field==null || !field.declaringType().equals(type) || !field.signature().equals(signature) || field.isStatic()!=isStatic)
      throw new IllegalStateException("Unexpected Java field: "+type.name()+"."+name);
    return field;
  }
  static void inspectRendererLayout(long base) throws Exception {
    long app=u32(base+0x21ef1e0L),manager=u32(app+8),engine=u32(app+4),renderer=u32(engine);
    if(app==0 || manager==0 || engine==0 || renderer==0 || u32(manager)!=base+0x21735a4L ||
       u32(renderer)!=base+0x21888b8L)
      throw new IllegalStateException("Renderer native owner/type unavailable");
    byte[] raw=memory(renderer+0x1c,0x54);
    ByteBuffer data=ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN);
    int[] logical={data.getInt(0),data.getInt(4),data.getInt(8),data.getInt(12)};
    int[] physical={data.getInt(0x28),data.getInt(0x2c),data.getInt(0x30),data.getInt(0x34)};
    float ox=data.getFloat(0x4c),oy=data.getFloat(0x50);
    if(!Float.isFinite(ox)||!Float.isFinite(oy)) throw new IllegalStateException("Renderer offsets not finite");
    for(int[] rect:List.of(logical,physical))
      if(Math.abs((long)rect[2]-rect[0])==0 || Math.abs((long)rect[3]-rect[1])==0 ||
         Math.abs((long)rect[2]-rect[0])>65536 || Math.abs((long)rect[3]-rect[1])>65536)
        throw new IllegalStateException("Renderer rectangle spans unavailable");
    ReferenceType framework=uniqueType("com.vshower.rann.RMFrameworkActivity");
    Field nf=exactField(framework,"N","Lcom/vshower/rann/b;",true);
    ObjectReference view=(ObjectReference)framework.getValue(nf);
    if(view==null || !view.referenceType().name().equals("com.vshower.rann.b"))
      throw new IllegalStateException("Original renderer view identity unavailable");
    Field mf=exactField(view.referenceType(),"m","Lcom/vshower/rann/RMFrameworkActivity;",false);
    ObjectReference activity=(ObjectReference)view.getValue(mf);
    if(activity==null || !activity.referenceType().name().equals("com.vshower.instrumented.InstrumentedActivity"))
      throw new IllegalStateException("Instrumented Activity/view association unavailable");
    if(!thread.frame(0).thisObject().equals(touchLayoutOnly?activity:view))
      throw new IllegalStateException("Snapshot receiver does not match verified view/Activity");
    List<Field> flags=new ArrayList<>();
    for(String name:List.of("F","x","z","A","t","u")) flags.add(exactField(framework,name,"Z",false));
    for(String name:List.of("y","w")) flags.add(exactField(framework,name,"I",false));
    Field pf=exactField(framework,"p","Lcom/vshower/rann/RMEditBox;",false);flags.add(pf);
    Map<Field,Value> values=activity.getValues(flags);
    if(((BooleanValue)values.get(flags.get(3))).value() || !((BooleanValue)values.get(flags.get(4))).value() ||
       !((BooleanValue)values.get(flags.get(5))).value()) throw new IllegalStateException("Activity lifecycle/touch flags not resumed");
    ObjectReference edit=(ObjectReference)values.get(pf);boolean keyboard=false;Field em=null,en=null;
    if(edit==null) throw new IllegalStateException("Original touch conversion requires its edit-box object");
    Value editOwner=null,editFlag=null;
    if(edit!=null) {
      ReferenceType et=uniqueType("com.vshower.rann.RMEditBox");
      em=exactField(et,"m","Lcom/vshower/rann/RMFrameworkActivity;",false);en=exactField(et,"n","Z",false);
      editOwner=edit.getValue(em);editFlag=edit.getValue(en);
      if(editOwner!=null && !editOwner.equals(activity)) throw new IllegalStateException("Edit box belongs to another Activity");
      keyboard=editOwner!=null && ((BooleanValue)editFlag).value();
    }
    ReferenceType version=uniqueType("android.os.Build$VERSION");
    int sdk=((IntegerValue)version.getValue(exactField(version,"SDK_INT","I",true))).value();
    ReferenceType androidView=uniqueType("android.view.View");
    if(sdk!=25 || androidView.classLoader()!=null) throw new IllegalStateException("Unverified framework accessor version/loader");
    Field attachField=exactField(androidView,"mAttachInfo","Landroid/view/View$AttachInfo;",false);
    ObjectReference attach=(ObjectReference)view.getValue(attachField);
    ReferenceType attachType=uniqueType("android.view.View$AttachInfo"),rootType=uniqueType("android.view.ViewRootImpl");
    if(attach==null || !attach.referenceType().equals(attachType)) throw new IllegalStateException("View attachment unavailable");
    Field rootField=exactField(attachType,"mViewRootImpl","Landroid/view/ViewRootImpl;",false);
    ObjectReference root=(ObjectReference)attach.getValue(rootField);
    List<Field> attachFields=new ArrayList<>();
    attachFields.add(exactField(attachType,"mRootView","Landroid/view/View;",false));
    attachFields.add(exactField(attachType,"mWindowLeft","I",false));attachFields.add(exactField(attachType,"mWindowTop","I",false));
    attachFields.add(exactField(attachType,"mApplicationScale","F",false));attachFields.add(exactField(attachType,"mScalingRequired","Z",false));
    Map<Field,Value> av=attach.getValues(attachFields);
    if(root==null || !root.referenceType().equals(rootType) ||
       !root.getValue(exactField(rootType,"mAttachInfo","Landroid/view/View$AttachInfo;",false)).equals(attach) ||
       !root.getValue(exactField(rootType,"mView","Landroid/view/View;",false)).equals(av.get(attachFields.get(0))))
      throw new IllegalStateException("View root/attachment association unavailable");
    List<Field> rootFields=List.of(exactField(rootType,"mCurScrollY","I",false),
      exactField(rootType,"mTranslator","Landroid/content/res/CompatibilityInfo$Translator;",false),
      exactField(rootType,"mWinFrame","Landroid/graphics/Rect;",false),
      exactField(rootType,"mAttachInfo","Landroid/view/View$AttachInfo;",false),
      exactField(rootType,"mView","Landroid/view/View;",false));
    Map<Field,Value> rv=root.getValues(rootFields);
    if(!rv.get(rootFields.get(3)).equals(attach)||!rv.get(rootFields.get(4)).equals(av.get(attachFields.get(0))))
      throw new IllegalStateException("Window root association changed");
    ObjectReference winFrame=(ObjectReference)rv.get(rootFields.get(2));
    ReferenceType rectType=uniqueType("android.graphics.Rect");List<Field> frameFields=new ArrayList<>();
    for(String name:List.of("left","top","right","bottom")) frameFields.add(exactField(rectType,name,"I",false));
    if(winFrame==null || !winFrame.referenceType().equals(rectType)) throw new IllegalStateException("Window frame unavailable");
    Map<Field,Value> wv=winFrame.getValues(frameFields);
    ObjectReference translator=(ObjectReference)rv.get(rootFields.get(1));String compat="none";
    List<Field> translatorFields=null;Map<Field,Value> tv=null;
    if(translator!=null) {
      ReferenceType tt=uniqueType("android.content.res.CompatibilityInfo$Translator");
      if(!translator.referenceType().equals(tt)) throw new IllegalStateException("Compatibility translator type unavailable");
      translatorFields=List.of(exactField(tt,"applicationScale","F",false),exactField(tt,"applicationInvertedScale","F",false));
      tv=translator.getValues(translatorFields);compat=tv.values().toString();
    }
    // API25 AOSP accessor is a pure stored RenderNode property read. No game
    // getter, cache refresh, GL operation, callback or mutation is invoked.
    float translation=((FloatValue)view.invokeMethod(thread,method(androidView,"getTranslationY","()F"),
      List.of(),ObjectReference.INVOKE_SINGLE_THREADED|ObjectReference.INVOKE_NONVIRTUAL)).value();
    if(!Float.isFinite(translation)) throw new IllegalStateException("View translation not finite");
    String touch="physicalToActivityLocal=unproved";
    ObjectReference touchEvent=null;ReferenceType touchType=null;float[] touchCoords=null;int[] touchIdentity=null;
    if(touchLayoutOnly) {
      ObjectReference event=(ObjectReference)thread.frame(0).getArgumentValues().get(0);
      ReferenceType motion=uniqueType("android.view.MotionEvent");
      if(event==null || !event.referenceType().equals(motion) || motion.classLoader()!=null)
        throw new IllegalStateException("Framework MotionEvent unavailable");
      int count=((IntegerValue)event.invokeMethod(thread,method(motion,"getPointerCount","()I"),List.of(),ObjectReference.INVOKE_SINGLE_THREADED)).value();
      int action=((IntegerValue)event.invokeMethod(thread,method(motion,"getActionMasked","()I"),List.of(),ObjectReference.INVOKE_SINGLE_THREADED)).value();
      int index=((IntegerValue)event.invokeMethod(thread,method(motion,"getActionIndex","()I"),List.of(),ObjectReference.INVOKE_SINGLE_THREADED)).value();
      if(count!=1 || action!=0 || index!=0) throw new IllegalStateException("Single actual DOWN event required");
      int pointerId=((IntegerValue)event.invokeMethod(thread,method(motion,"getPointerId","(I)I"),List.of(vm.mirrorOf(0)),ObjectReference.INVOKE_SINGLE_THREADED)).value();
      if(pointerId<0) throw new IllegalStateException("Actual DOWN pointer identity unavailable");
      touchIdentity=new int[]{count,action,index,pointerId};
      float[] coords=new float[4];int ci=0;
      for(String getter:List.of("getX","getY","getRawX","getRawY")) {
        coords[ci]=((FloatValue)event.invokeMethod(thread,method(motion,getter,"()F"),List.of(),ObjectReference.INVOKE_SINGLE_THREADED)).value();
        if(!Float.isFinite(coords[ci++])) throw new IllegalStateException("Touch coordinate not finite");
      }
      touchEvent=event;touchType=motion;touchCoords=coords;
      boolean f=((BooleanValue)values.get(flags.get(0))).value(),x=((BooleanValue)values.get(flags.get(1))).value();
      boolean z=((BooleanValue)values.get(flags.get(2))).value();
      int y=((IntegerValue)values.get(flags.get(6))).value(),w=((IntegerValue)values.get(flags.get(7))).value();
      ReferenceType build=uniqueType("android.os.Build");
      String model=((StringReference)build.getValue(exactField(build,"MODEL","Ljava/lang/String;",true))).value();
      int nx=(int)coords[0],ny=(int)coords[1]-(int)translation+(keyboard&&!x?w:0)+(!f||model.equalsIgnoreCase("801SH")?(z?y:0):0);
      float lx=ox+((float)(nx-physical[0])*Math.abs((float)((long)logical[2]-logical[0])))/Math.abs((float)((long)physical[2]-physical[0]));
      float ly=oy+((float)(ny-physical[1])*Math.abs((float)((long)logical[3]-logical[1])))/Math.abs((float)((long)physical[3]-physical[1]));
      touch=String.format("actualPointerId=%d actualActionIndex=%d actualDownLocal=[%f,%f] actualDownRaw=[%f,%f] reconstructedJNI=[%d,%d] reconstructedLogical=[%d,%d] physicalToActivityLocal=observed_this_event_only nativeContactRegistration=unproved",
        pointerId,index,coords[0],coords[1],coords[2],coords[3],nx,ny,(int)lx,(int)ly);
      if(episodeTouchOnly) observedLogicalDown=new int[]{(int)lx,(int)ly};
    }
    float translationAgain=((FloatValue)view.invokeMethod(thread,method(androidView,"getTranslationY","()F"),
      List.of(),ObjectReference.INVOKE_SINGLE_THREADED|ObjectReference.INVOKE_NONVIRTUAL)).value();
    if(Float.floatToIntBits(translationAgain)!=Float.floatToIntBits(translation))
      throw new IllegalStateException("Framework translation changed");
    if(touchEvent!=null) {
      int[] againIdentity={
        ((IntegerValue)touchEvent.invokeMethod(thread,method(touchType,"getPointerCount","()I"),List.of(),ObjectReference.INVOKE_SINGLE_THREADED)).value(),
        ((IntegerValue)touchEvent.invokeMethod(thread,method(touchType,"getActionMasked","()I"),List.of(),ObjectReference.INVOKE_SINGLE_THREADED)).value(),
        ((IntegerValue)touchEvent.invokeMethod(thread,method(touchType,"getActionIndex","()I"),List.of(),ObjectReference.INVOKE_SINGLE_THREADED)).value(),
        ((IntegerValue)touchEvent.invokeMethod(thread,method(touchType,"getPointerId","(I)I"),List.of(vm.mirrorOf(0)),ObjectReference.INVOKE_SINGLE_THREADED)).value()};
      if(!Arrays.equals(touchIdentity,againIdentity)) throw new IllegalStateException("Observed touch identity changed");
      if(!thread.frame(0).getArgumentValues().get(0).equals(touchEvent) ||
        ((IntegerValue)touchEvent.invokeMethod(thread,method(touchType,"getPointerCount","()I"),List.of(),ObjectReference.INVOKE_SINGLE_THREADED)).value()!=1 ||
        ((IntegerValue)touchEvent.invokeMethod(thread,method(touchType,"getActionMasked","()I"),List.of(),ObjectReference.INVOKE_SINGLE_THREADED)).value()!=0)
        throw new IllegalStateException("Observed touch identity/action changed");
      int ci=0;
      for(String getter:List.of("getX","getY","getRawX","getRawY")) {
        float again=((FloatValue)touchEvent.invokeMethod(thread,method(touchType,getter,"()F"),List.of(),ObjectReference.INVOKE_SINGLE_THREADED)).value();
        if(Float.floatToIntBits(again)!=Float.floatToIntBits(touchCoords[ci++]))
          throw new IllegalStateException("Observed touch coordinates changed");
      }
    }
    if(u32(base+0x21ef1e0L)!=app || u32(app+8)!=manager || u32(manager)!=base+0x21735a4L ||
       u32(app+4)!=engine || u32(engine)!=renderer || u32(renderer)!=base+0x21888b8L ||
       !Arrays.equals(raw,memory(renderer+0x1c,0x54)) || !framework.getValue(nf).equals(view) ||
       !view.getValue(mf).equals(activity) || !activity.getValues(flags).equals(values) ||
       !view.getValue(attachField).equals(attach) || !attach.getValue(rootField).equals(root) ||
       !attach.getValues(attachFields).equals(av) || !root.getValues(rootFields).equals(rv) ||
       !winFrame.getValues(frameFields).equals(wv) || (translator!=null&&!translator.getValues(translatorFields).equals(tv)) ||
       (edit!=null && (!Objects.equals(edit.getValue(em),editOwner)||!edit.getValue(en).equals(editFlag))))
      throw new IllegalStateException("Renderer/layout snapshot changed");
    System.out.printf("Renderer layout diagnostic OES2owner=global_app_engine_rechecked logicalRect=%s physicalRect=%s logicalOffsets=[%f,%f] SDK=%d translationY=%f translationProvenance=pure_Android_View_RenderNode_accessor F=%s x=%s z=%s y=%s w=%s keyboard=%s %s%n",
      Arrays.toString(logical),Arrays.toString(physical),ox,oy,sdk,translation,values.get(flags.get(0)),values.get(flags.get(1)),
      values.get(flags.get(2)),values.get(flags.get(6)),values.get(flags.get(7)),keyboard,touch);
    System.out.printf("Framework window diagnostic attachmentOrigin=[%s,%s] applicationScale=%s scalingRequired=%s scrollY=%s frame=[%s,%s,%s,%s] compatibilityTranslator=%s viewRootAssociation=rechecked hierarchyToPhysical=unproved%n",
      av.get(attachFields.get(1)),av.get(attachFields.get(2)),av.get(attachFields.get(3)),av.get(attachFields.get(4)),rv.get(rootFields.get(0)),
      wv.get(frameFields.get(0)),wv.get(frameFields.get(1)),wv.get(frameFields.get(2)),wv.get(frameFields.get(3)),compat);
  }
  static boolean episodeOwnerStable(long base,long app,long manager,long current,long currentControl,long currentControlVptr,long scene,long control,long controlVptr) throws Exception {
    return u32(base+0x21ef1e0L)==app && u32(app+8)==manager &&
      u32(manager)==base+0x21735a4L && u32(manager+0x34)==current && u32(manager+0x38)==currentControl &&
      u32(currentControl)==currentControlVptr && (int)u32(currentControl+4)>=0 &&
      u32(current)==base+0x216f90cL && u32(current+0x660)==7 &&
      u32(current+0x658)==scene && u32(current+0x65c)==control &&
      u32(scene)==base+0x215352cL && u32(control)==controlVptr && controlVptr==base+0x216faa4L &&
      (int)u32(control+4)>=0 && scene==control+0x10;
  }
  static boolean episodeCombatOwnerStable(long base,long model,long modelControl,long combat,long combatControl) throws Exception {
    // Original singleton wpRet ELF21d42f4 and default-delete model control.
    // COMBAT is embedded in its emplace control, unlike the model pointer field.
    return u32(base+0x21d42f4L)==model && u32(base+0x21d42f8L)==modelControl &&
      u32(modelControl)==base+0x21532bcL && (int)u32(modelControl+4)>=0 && u32(modelControl+0xc)==model &&
      u32(model+0x24)==combat && u32(model+0x28)==combatControl &&
      u32(combatControl)==base+0x2153248L && (int)u32(combatControl+4)>=0 && combat==combatControl+0xc;
  }
  /** UI-only observer: no combat-model, actor, modal or background traversal.
   * Read-only evidence of panel state; never authorizes an input. */
  static void inspectEpisodeControls(long base) throws Exception {
    long app=u32(base+0x21ef1e0L);
    if(app==0 || (app&3)!=0)throw new IllegalStateException("Episode controls app unavailable");
    long manager=u32(app+8);
    if(manager==0 || (manager&3)!=0 || u32(manager)!=base+0x21735a4L)
      throw new IllegalStateException("Episode controls scene manager unproved");
    long current=u32(manager+0x34),currentControl=u32(manager+0x38);
    if(current==0 || currentControl==0 || (current&3)!=0 || (currentControl&3)!=0 ||
       u32(current)!=base+0x216f90cL || (int)u32(currentControl+4)<0 || u32(current+0x660)!=7)
      throw new IllegalStateException("Episode controls requires owned CSRSceneGame mode7; no UI reads");
    long currentControlVptr=u32(currentControl),game=u32(current+0x658),control=u32(current+0x65c);
    if(game==0 || control==0 || (game&3)!=0 || (control&3)!=0 ||
       u32(game)!=base+0x215352cL || u32(control)!=base+0x216faa4L ||
       (int)u32(control+4)<0 || game!=control+0x10)
      throw new IllegalStateException("Episode controls child emplace owner unproved or expired");
    long controlVptr=u32(control),pause=u32(game+0x140),gameMode=u32(game+0x2ec);
    String snapshot=episodeControlsSnapshot(base,game);
    if(!episodeOwnerStable(base,app,manager,current,currentControl,currentControlVptr,game,control,controlVptr) ||
       u32(game+0x140)!=pause || u32(game+0x2ec)!=gameMode)
      throw new IllegalStateException("Episode controls owner/fields changed; discard snapshot");
    System.out.printf("Episode controls sceneELFvptr=215352c gameMode2ec=%d pause140=%x combatModelRead=false actorsRead=false nativeGettersCalled=false inputAuthorization=none%n",gameMode,pause);
    System.out.print(snapshot);
  }
  static void inspectEpisodeScene(long base) throws Exception {
    // Live default observer and original CSRSceneGame.OnInit case7 prove wrapper
    // ownership. Episode directly inherits CSRGameBase, but is the wrapper child.
    long app=u32(base+0x21ef1e0L);
    if(app==0 || (app&3)!=0) throw new IllegalStateException("Episode app unavailable");
    long manager=u32(app+8);
    if(manager==0 || (manager&3)!=0 || u32(manager)!=base+0x21735a4L)
      throw new IllegalStateException("unexpected Episode scene manager");
    long current=u32(manager+0x34),currentControl=u32(manager+0x38);
    if(current==0 || currentControl==0 || (current&3)!=0 || (currentControl&3)!=0 ||
       u32(current)!=base+0x216f90cL || (int)u32(currentControl+4)<0 || u32(current+0x660)!=7)
      throw new IllegalStateException("current scene is not nonexpired owned CSRSceneGame mode7; no Episode reads");
    long currentControlVptr=u32(currentControl);
    long scene=u32(current+0x658),control=u32(current+0x65c);
    if(scene==0 || control==0 || (scene&3)!=0 || (control&3)!=0 ||
       u32(scene)!=base+0x215352cL || u32(control)!=base+0x216faa4L ||
       (int)u32(control+4)<0 || scene!=control+0x10)
      throw new IllegalStateException("Episode child emplace owner unproved or expired");
    // make_shared Gb e3da76 uses control+10 (alignment), not assumed control+c.
    long controlVptr=u32(control);
    // Proven owner path documented in episode-combat-model-owner.md; no heap scan
    // or native getter. Selected combat can remain present during ending dialogue.
    long model=u32(base+0x21d42f4L),modelControl=u32(base+0x21d42f8L);
    if(model==0 || modelControl==0 || (model&3)!=0 || (modelControl&3)!=0 ||
       u32(modelControl)!=base+0x21532bcL || (int)u32(modelControl+4)<0 || u32(modelControl+0xc)!=model)
      throw new IllegalStateException("Episode model owner unproved or expired");
    long combat=u32(model+0x24),combatControl=u32(model+0x28);
    if(combat==0 || combatControl==0 || (combat&3)!=0 || (combatControl&3)!=0 ||
       u32(combatControl)!=base+0x2153248L || (int)u32(combatControl+4)<0 || combat!=combatControl+0xc)
      throw new IllegalStateException("Episode current COMBAT owner unproved or expired");
    String combatId=cppString(combat);
    if(combatId.isEmpty() || !combatId.matches("[A-Za-z0-9_]+"))
      throw new IllegalStateException("invalid bounded Episode combat ID");
    int left=(int)u32(scene+0x2e4),right=(int)u32(scene+0x2e8);
    long pause=u32(scene+0x140);
    if(left < -1 || right < -1) throw new IllegalStateException("invalid signed Episode remain fields");
    String inputGuard=episodeInputSnapshot(base,scene,left,right,pause);
    long holder=base+0x21e57f8L,modal=0,modalControl=0,primary=0,secondary=0,back=0,top=0,topVptr=0;
    boolean modalSafe=false;
    String modalLimit="";
    try {
      // Same modal-handler owner/list chain as inspectGuideState; bounded top only.
      modal=u32(holder); modalControl=u32(holder+4);
      if(modal==0 || modalControl==0 || (modal&3)!=0 || (modalControl&3)!=0 ||
         u32(modalControl)!=base+0x2186a38L || (int)u32(modalControl+4)<0 || u32(modalControl+0xc)!=modal)
        throw new IllegalStateException("unproved or expired modal owner");
      primary=u32(modal+0xc); secondary=u32(modal+0x18);
      if(primary>32 || secondary>32) throw new IllegalStateException("modal list exceeds32 bound");
      long count=secondary>0?secondary:primary;
      if(count>0) {
        back=u32(modal+(secondary>0?0x10:4));
        if(back==0 || (back&3)!=0) throw new IllegalStateException("invalid modal back node");
        top=u32(back+8);
        if(top==0 || (top&3)!=0) throw new IllegalStateException("invalid modal top object");
        topVptr=u32(top);
      }
      modalSafe=true;
    } catch(IllegalArgumentException | IllegalStateException unsafe) {
      modalLimit=unsafe.getMessage();
    }
    String materials=episodeMaterialsOnly ? episodeMaterialSnapshot(base,scene) : "";
    if(episodeBadgeOnly) materials=episodeHealSource==null?episodeHealSourceSnapshot(base,scene):episodeHealSourceSnapshot(base,scene,episodeHealSource);
    if(episodeFeverOnly) materials=episodeFeverSnapshot(base,scene);
    if(episodeHealSource!=null && !episodeBadgeOnly) materials+=episodeHealSourceSnapshot(base,scene,episodeHealSource);
    String exchange=episodeExchangeOnly ? episodeExchangeCaughtSnapshot(base,scene)+episodeExchangeReserveSnapshot(base,scene)+episodeExchangeUiSnapshot(base,scene) : "";
    if(!episodeOwnerStable(base,app,manager,current,currentControl,currentControlVptr,scene,control,controlVptr) ||
       !episodeCombatOwnerStable(base,model,modelControl,combat,combatControl) || !cppString(combat).equals(combatId) ||
       (int)u32(scene+0x2e4)!=left || (int)u32(scene+0x2e8)!=right || u32(scene+0x140)!=pause)
      throw new IllegalStateException("Episode owner/fields changed; discard snapshot");
    if(modalSafe && (u32(holder)!=modal || u32(holder+4)!=modalControl ||
       u32(modalControl)!=base+0x2186a38L || (int)u32(modalControl+4)<0 || u32(modalControl+0xc)!=modal ||
       u32(modal+0xc)!=primary || u32(modal+0x18)!=secondary ||
       ((primary>0 || secondary>0) && (u32(modal+(secondary>0?0x10:4))!=back ||
          u32(back+8)!=top || u32(top)!=topVptr))))
      throw new IllegalStateException("Episode modal owner/fields changed; discard snapshot");
    if(!episodeOwnerStable(base,app,manager,current,currentControl,currentControlVptr,scene,control,controlVptr) ||
       !episodeCombatOwnerStable(base,model,modelControl,combat,combatControl) || !cppString(combat).equals(combatId) ||
       (int)u32(scene+0x2e4)!=left || (int)u32(scene+0x2e8)!=right || u32(scene+0x140)!=pause)
      throw new IllegalStateException("Episode final owner/fields changed; discard snapshot");
    String terminal=left==-1 || right==-1 ? "uninitialized" :
      left==0 ? "loss-condition" : right==0 ? "win-condition" : "no-terminal-evidence";
    System.out.printf("Episode sceneELFvptr=215352c selectedCombatId=%s leftRemain2e4=%d rightRemain2e8=%d pause140=%x terminal=%s%n",
      combatId,left,right,pause,terminal);
    System.out.print(inputGuard);
    if(modalSafe) System.out.printf("Episode modalPrimary=%d modalSecondary=%d topELFvptr=%x%n",
      primary,secondary,topVptr==0?0:topVptr-base);
    else System.out.printf("Episode modalSnapshot=unavailable reason=%s%n",modalLimit);
    System.out.println("Episode limits: wrapper manager control branch has pair/nonexpired checks only; exact child emplace ownership verified. " +
      "Selected combat ID can persist during ending dialogue; terminal fields do not authorize attacks; scene vptr does not establish active combat.");
    if(episodeMaterialsOnly || episodeBadgeOnly || episodeFeverOnly) System.out.print(materials);
    System.out.print(exchange);
  }
  static String episodeInputSnapshot(long base,long game,int left,int right,long pause) throws Exception {
    String background=episodeBackgroundPauseSnapshot(base,game);
    int started=memory(game+0x3d1,1)[0]&255,state=memory(game+0x13c,1)[0]&255;
    long skillInhibit=u32(game+0x138);
    // IsSkillReserve G9e6dc8 tests both inline serial halves; ReserveSkill
    // G9e6ab0 stores the selected actor serial only after nonempty effects.
    // No pending-record pointer or effect-list dereference is needed here.
    long reserveLow=u32(game+0x3d8),reserveHigh=u32(game+0x3dc);
    long caught=u32(game+0x198),count=u32(game+0x184),sentinel=game+0x17c,first=u32(game+0x180),node=first;
    if(started>1 || count>16) throw new IllegalStateException("Episode input fields outside bound");
    Set<Long> visited=new HashSet<>();int inputable=0;
    StringBuilder inputActors=new StringBuilder();
    while(node!=sentinel && visited.size()<16) {
      if(node==0 || !visited.add(node)) throw new IllegalStateException("Episode input list null/cycle");
      long actor=u32(node+8),actorControl=u32(node+0xc);
      if(actor==0 || actorControl==0 || actor!=actorControl+0x10 || u32(actor)!=base+0x214a3fcL ||
         u32(actorControl)!=base+0x214bdc4L || (int)u32(actorControl+4)<0)
        throw new IllegalStateException("Episode input Hunter owner unproved");
      long camp=u32(actor+0x988),binding=u32(actor+0xa6c);float hp=f32(actor+0x8b0);
      long serialLow=u32(actor+0x880),serialHigh=u32(actor+0x884);
      byte[] skillSwitches=memory(actor+0xa7c,2);
      long pose=u32(actor+0xa14),iconControl=u32(actor+0xa70);int iconVisible=-1;
      long skillDrawable=0,skillDrawableControl=0;byte[] skillAlpha=null,skillHidden=null;int skillRaw238=-1,skillRawAlpha=-1;
      if(binding!=0) {
        if(iconControl==0 || binding!=iconControl+0x10 || u32(binding)!=base+0x214db40L ||
           u32(iconControl)!=base+0x2149ac8L || (int)u32(iconControl+4)<0)
          throw new IllegalStateException("Input-front skill icon owner unproved");
        iconVisible=memory(binding+0x6c,1)[0]&255;
        skillDrawable=u32(binding+0x60);skillDrawableControl=u32(binding+0x64);
        if(skillDrawable==0 || skillDrawableControl==0 || skillDrawable!=skillDrawableControl+0x10 ||
           u32(skillDrawable)!=base+0x213baccL || u32(skillDrawableControl)!=base+0x2139540L || (int)u32(skillDrawableControl+4)<0)
          throw new IllegalStateException("Input-front skill drawable owner unproved");
        skillAlpha=memory(skillDrawable+0xb4,12);skillRaw238=memory(skillDrawable+0x238,1)[0]&255;
        skillHidden=memory(skillDrawable+0x270,2);
        skillRawAlpha=memory(skillDrawable+0x1f8,1)[0]&255;
      }
      String resId=(episodeSkillsOnly||episodeExchangeOnly)?cppString(actor+0x888):"";
      if(camp>1 || !Float.isFinite(hp)) throw new IllegalStateException("Episode input Hunter fields invalid");
      if(camp==0 && binding!=0 && hp>0) inputable++;
      if(episodeSkillsOnly||episodeExchangeOnly) {
        inputActors.append(String.format("Episode input member camp=%d serial=%08x%08x resId=%s hp=%f bindingPresent=%s viewportMatch=unproved%n",
          camp,serialHigh,serialLow,resId,hp,binding!=0));
        inputActors.append(episodeSerialTarget(base,game,serialLow,serialHigh,actor));
        inputActors.append(episodeActorStateSnapshot(base,actor));
        inputActors.append(episodeFrontViewportSnapshot(base,actor));
      }
      inputActors.append(String.format(Locale.ROOT,"Episode input skill bytes camp=%d serial=%08x%08x hp=%f policyA7c=%d enabledA7d=%d poseA14=%d iconVisible=%s finalAlphaAndEligibility=unproved%n",
        camp,serialHigh,serialLow,hp,skillSwitches[0]&255,skillSwitches[1]&255,pose,iconVisible<0?"unavailable":Integer.toString(iconVisible)));
      if(skillAlpha!=null) {
        ByteBuffer sa=ByteBuffer.wrap(skillAlpha).order(ByteOrder.LITTLE_ENDIAN);
        inputActors.append(String.format(Locale.ROOT,"Episode input skill drawable raw238=%d effectiveHidden270=%d localHidden271=%d drawAlpha1f8=%d rawOpacityFactors=[%f,%f,%f] renderedChildrenAndCallbackAlpha=unproved%n",
          skillRaw238,skillHidden[0]&255,skillHidden[1]&255,skillRawAlpha,sa.getFloat(),sa.getFloat(),sa.getFloat()));
      }
      if(u32(node+8)!=actor || u32(node+0xc)!=actorControl || u32(actor)!=base+0x214a3fcL ||
         u32(actorControl)!=base+0x214bdc4L || (int)u32(actorControl+4)<0 || u32(actor+0x988)!=camp ||
         u32(actor+0xa6c)!=binding || f32(actor+0x8b0)!=hp ||
         !Arrays.equals(skillSwitches,memory(actor+0xa7c,2)) ||
         u32(actor+0xa14)!=pose || u32(actor+0xa70)!=iconControl ||
         (binding!=0 && (u32(binding)!=base+0x214db40L || u32(iconControl)!=base+0x2149ac8L ||
          (int)u32(iconControl+4)<0 || (memory(binding+0x6c,1)[0]&255)!=iconVisible ||
          u32(binding+0x60)!=skillDrawable || u32(binding+0x64)!=skillDrawableControl ||
          u32(skillDrawable)!=base+0x213baccL || u32(skillDrawableControl)!=base+0x2139540L || (int)u32(skillDrawableControl+4)<0 ||
          !Arrays.equals(skillAlpha,memory(skillDrawable+0xb4,12)) || (memory(skillDrawable+0x238,1)[0]&255)!=skillRaw238 ||
          !Arrays.equals(skillHidden,memory(skillDrawable+0x270,2)) || (memory(skillDrawable+0x1f8,1)[0]&255)!=skillRawAlpha)) ||
         ((episodeSkillsOnly||episodeExchangeOnly) && (u32(actor+0x880)!=serialLow || u32(actor+0x884)!=serialHigh || !cppString(actor+0x888).equals(resId))))
        throw new IllegalStateException("Episode input Hunter changed");
      node=u32(node+4);
    }
    if(node!=sentinel || visited.size()!=count || u32(game+0x180)!=first || u32(game+0x184)!=count ||
       (memory(game+0x3d1,1)[0]&255)!=started || (memory(game+0x13c,1)[0]&255)!=state || u32(game+0x198)!=caught ||
       u32(game+0x3d8)!=reserveLow || u32(game+0x3dc)!=reserveHigh)
      throw new IllegalStateException("Episode input state changed or exceeds bound");
    // Original OnRefresh permits -1: it rejects zero, not nonpositive counters.
    boolean armed=started==1 && (state&0x14)==0 && caught==0 && pause==0 && left!=0 && right!=0 && inputable>0;
    String reserve=String.format("Episode reserve diagnostic serial3d8=%08x%08x IsSkillReserve=%s owner=verified_Episode_child predicate=inline_serial_nonzero effectPurchase=unproved%n",
      reserveHigh,reserveLow,reserveLow!=0 || reserveHigh!=0);
    if(u32(game+0x138)!=skillInhibit) throw new IllegalStateException("Episode skill inhibition counter changed");
    return String.format("Episode skill policy inhibitCounter138=%d projectedSetSkillOn=%s source=GameBase_SetSkillOn nativeVisibilityAndEligibility=unproved%n",
      skillInhibit,skillInhibit==0)+background+reserve+String.format("Episode armed=%s started3d1=%d state13c=%x caught198=%x inputCount184=%d liveInputablePlayerHunters=%d%n",
      armed?"yes":"no",started,state,caught,count,inputable)+inputActors;
  }
  static String episodeBackgroundPauseSnapshot(long base,long game) throws Exception {
    // Original GameBase constructor G9c11da..121a: separate CMUpdatable0x280
    // named Opp, control0x10/default-delete, pointer at+c. IsBGPaused G9dfb1e
    // reads this object's278, independently of GameBase.pause140.
    long object=u32(game+0x284),control=u32(game+0x288);
    if(object==0 || control==0 || (object&3)!=0 || (control&3)!=0 ||
       u32(object)!=base+0x213a874L || u32(control)!=base+0x2136084L ||
       (int)u32(control+4)<0 || u32(control+0xc)!=object)
      throw new IllegalStateException("Episode background CMUpdatable owner unproved");
    byte[] raw=memory(object,0x280);
    long reasons=Integer.toUnsignedLong(ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN).getInt(0x278));
    if(u32(game+0x284)!=object || u32(game+0x288)!=control ||
       u32(control)!=base+0x2136084L || (int)u32(control+4)<0 || u32(control+0xc)!=object ||
       !Arrays.equals(raw,memory(object,0x280)))
      throw new IllegalStateException("Episode background owner/pause changed");
    return String.format("Episode background diagnostic object=CMUpdatable owner=separate_default_delete_verified pause278=%x IsBGPaused8=%s gamePause140=separate%n",
      reasons,(reasons&8)!=0);
  }
  static String episodeFrontViewportSnapshot(long base,long actor) throws Exception {
    // Listener9f76ae slot9f7954/ADD9f76b0 -> GOT21bafec -> global21ff1e0
    // (ELF21ef1e0). Then app+4 -> engine[0] renderer, inline CRMRect+18.
    long app=u32(base+0x21ef1e0L),manager=u32(app+8),engine=u32(app+4),renderer=u32(engine);
    if(app==0 || manager==0 || engine==0 || renderer==0 ||
       u32(manager)!=base+0x21735a4L || u32(renderer)!=base+0x21888b8L)
      throw new IllegalStateException("Episode viewport renderer owner unproved");
    byte[] viewportBytes=memory(renderer+0x18,20);
    ByteBuffer v=ByteBuffer.wrap(viewportBytes).order(ByteOrder.LITTLE_ENDIAN);
    int x=v.getInt(4),y=v.getInt(8),right=v.getInt(12),bottom=v.getInt(16);
    long width=Math.abs((long)right-x),height=Math.abs((long)bottom-y);
    if(width==0 || height==0 || width>65536 || height>65536)
      throw new IllegalStateException("Episode viewport spans outside bound");
    // CMVec4Rect(CRMRect)753c16 preserves origin and adds absolute spans.
    float[] viewport={x,y,(float)x+(float)width,(float)y+(float)height};
    long component=u32(actor+0xa28),owner=u32(actor+0xa2c);
    if(component==0 || owner==0 || component!=owner+0x10 || (int)u32(owner+4)<0)
      throw new IllegalStateException("Episode front component owner unavailable");
    boolean image=u32(component)==base+0x21363d4L && u32(owner)==base+0x2149a04L;
    boolean spine=u32(component)==base+0x2136510L && u32(owner)==base+0x21499dcL;
    if(!image && !spine) throw new IllegalStateException("Episode front component class unproved");
    long offset=image?0x64c:0x67c,drawable=u32(component+offset),control=u32(component+offset+4);
    if(drawable==0 || control==0 || (int)u32(control+4)<0 ||
       (image && (u32(drawable)!=base+0x2136948L || u32(control)!=base+0x2136468L || u32(control+0xc)!=drawable)) ||
       (spine && (drawable!=control+0x10 || u32(drawable)!=base+0x2138f30L || u32(control)!=base+0x21353acL)))
      throw new IllegalStateException("Episode front drawable concrete owner unproved");
    if((u32(u32(drawable)+0x90)&~1L)!=base+0x6fc810L ||
       (u32(u32(drawable)+0x94)&~1L)!=base+0x6fb0e0L ||
       (u32(u32(drawable)+0x60)&~1L)!=base+0x6fc560L)
      throw new IllegalStateException("Episode front GetArea cache consumer unproved");
    byte[] areaBytes=memory(drawable+0x1bc,16),relation=memory(component+0xb4,0x38);
    int flags=memory(drawable+0x60,1)[0]&255;
    ByteBuffer a=ByteBuffer.wrap(areaBytes).order(ByteOrder.LITTLE_ENDIAN);
    float[] bound={a.getFloat(),a.getFloat(),a.getFloat(),a.getFloat()};
    String ancestry=skillAncestrySnapshot(base,drawable,actor).replace("Episode skill ancestry","Episode front ancestry");
    // GetArea refresh consumes this drawable's area8, local1/world2 and
    // CalcAdditionalTrans16. Ancestor area8 is not a child GetArea input;
    // retain ancestor transform1/2 checks, without requiring their area caches.
    boolean clean=(flags&0x9b)==0 && ancestry.contains("diagnostic=root_reached") &&
      ancestry.contains("containsOwnedActor=true") &&
      ancestry.contains("transformMasksClear=true");
    boolean alignKnown=true;
    if(image) {
      ByteBuffer r=ByteBuffer.wrap(relation).order(ByteOrder.LITTLE_ENDIAN);
      int ax=r.getInt(0),ay=r.getInt(4);float px=r.getFloat(8),py=r.getFloat(12),w=r.getFloat(16),h=r.getFloat(20);
      alignKnown=ax>=0 && ax<=2 && ay>=0 && ay<=2;
      if(alignKnown) {
        float bx=ax==0?bound[0]:ax==1?bound[2]-w:(bound[0]+bound[2])*.5f-w*.5f;
        float by=ay==0?bound[1]:ay==1?bound[3]-h:(bound[1]+bound[3])*.5f-h*.5f;
        bound=new float[]{px+bx,py+by,px+bx+w,py+by+h};
      }
    }
    boolean finite=true;for(float f:bound) finite&=Float.isFinite(f);
    boolean qualified=clean && alignKnown && finite && bound[0]<=bound[2] && bound[1]<=bound[3];
    boolean intersects=!(bound[3]<viewport[1] || viewport[3]<bound[1] || bound[2]<viewport[0] || viewport[2]<bound[0]);
    if(u32(base+0x21ef1e0L)!=app || u32(app+8)!=manager || u32(app+4)!=engine || u32(engine)!=renderer ||
       u32(manager)!=base+0x21735a4L || u32(renderer)!=base+0x21888b8L ||
       !Arrays.equals(viewportBytes,memory(renderer+0x18,20)) || u32(actor+0xa28)!=component || u32(actor+0xa2c)!=owner ||
       u32(component)!=(image?base+0x21363d4L:base+0x2136510L) || u32(owner)!=(image?base+0x2149a04L:base+0x21499dcL) ||
       (int)u32(owner+4)<0 || u32(component+offset)!=drawable || u32(component+offset+4)!=control ||
       u32(drawable)!=(image?base+0x2136948L:base+0x2138f30L) || u32(control)!=(image?base+0x2136468L:base+0x21353acL) ||
       (int)u32(control+4)<0 || (image && u32(control+0xc)!=drawable) ||
       (memory(drawable+0x60,1)[0]&255)!=flags || !Arrays.equals(areaBytes,memory(drawable+0x1bc,16)) ||
       !Arrays.equals(relation,memory(component+0xb4,0x38)))
      throw new IllegalStateException("Episode front viewport snapshot changed");
    return String.format(Locale.ROOT,"Episode front viewport branch=%s viewport=%s reconstructedGetFrontBound=%s cleanCache=%s alignmentKnown=%s intersection=%s nativeGetterCalls=false nativeMatchedCandidate=unproved%n",
      image?"image_relation":"spine_area",Arrays.toString(viewport),Arrays.toString(bound),clean,alignKnown,
      qualified?Boolean.toString(intersects):"unavailable")+ancestry;
  }
  static String episodeMaterialSnapshot(long base,long game) throws Exception {
    int selectedSources=0;
    long first=u32(game+0x33c),count=u32(game+0x340),node=first;
    if(count>8) throw new IllegalStateException("Episode material group count exceeds8");
    Set<Long> groups=new HashSet<>();StringBuilder result=new StringBuilder();
    for(int i=0;node!=0 && i<8;i++) {
      if(!groups.add(node)) throw new IllegalStateException("Episode material group cycle");
      long group=u32(node+0x14),groupControl=u32(node+0x18);
      if(group==0 || groupControl==0 || u32(group)!=base+0x2149f68L || (int)u32(groupControl+4)<0)
        throw new IllegalStateException("Episode material group identity/owner unavailable");
      long groupControlVptr=u32(groupControl),sentinel=group+0x27c,member=u32(group+0x280),memberFirst=member;
      long camp=u32(group+0x2d0);
      float sp=f32(group+0x2bc),rate=f32(group+0x2c0),maxSP=f32(group+0x2c4);
      if(camp>1 || !Float.isFinite(sp) || !Float.isFinite(rate) || !Float.isFinite(maxSP) || sp<0 || rate<0 || maxSP<0)
        throw new IllegalStateException("Episode group Rage fields invalid");
      result.append(String.format("Episode Rage camp=%d SP=%f rate=%f maxSP=%f%n",camp,sp,rate,maxSP));
      Set<Long> members=new HashSet<>();
      while(member!=sentinel && members.size()<16) {
        if(member==0 || !members.add(member)) throw new IllegalStateException("Episode actor member cycle/null");
        long actor=u32(member+8),actorControl=u32(member+0xc);
        if(actor==0 || actorControl==0 || (int)u32(actorControl+4)<0)
          throw new IllegalStateException("Episode actor identity/owner unavailable");
        long actorVptr=u32(actor),actorControlVptr=u32(actorControl);
        if(actor!=actorControl+0x10 || !((actorVptr==base+0x214a3fcL && actorControlVptr==base+0x214bdc4L) ||
          (actorVptr==base+0x214a638L && actorControlVptr==base+0x214bd9cL)))
          throw new IllegalStateException("Episode actor emplace owner unproved");
        String resId=cppString(actor+0x888),groupId=cppString(actor+0x898);
        long serialLow=u32(actor+0x880),serialHigh=u32(actor+0x884);
        float hp=f32(actor+0x8b0);
        boolean selected=episodeTouchSourceSerial==0 || (serialHigh==0 && serialLow==episodeTouchSourceSerial);
        if(episodeTouchSourceSerial!=0 && selected) {
          if(camp!=0 || u32(actor+0x988)!=0 || actorVptr!=base+0x214a3fcL || !Float.isFinite(hp) || hp<=0)
            throw new IllegalStateException("Selected Episode source is not a living camp0 Hunter");
          selectedSources++;
        }
        long component=u32(actor+0xa28),componentControl=u32(actor+0xa2c);
        long componentVptr=component==0 ? 0 : u32(component);
        long componentControlVptr=componentControl==0 ? 0 : u32(componentControl);
        if(component!=0 && (componentControl==0 || (int)u32(componentControl+4)<0))
          throw new IllegalStateException("Episode draw component owner expired");
        if(component!=0 && (component!=componentControl+0x10 ||
          !((componentVptr==base+0x21363d4L && componentControlVptr==base+0x2149a04L) ||
            (componentVptr==base+0x2136510L && componentControlVptr==base+0x21499dcL))))
          throw new IllegalStateException("Episode draw component emplace owner unproved");
        if(!Float.isFinite(hp)) throw new IllegalStateException("Episode actor HP invalid");
        result.append(String.format("Episode material group=%s serial=%08x%08x resId=%s hp=%f actorELFvptr=%x actorControlELFvptr=%x componentELFvptr=%x%n",
          groupId,serialHigh,serialLow,resId,hp,actorVptr-base,actorControlVptr-base,componentVptr==0?0:componentVptr-base));
        // Selected mode preserves every material-list actor identity/owner
        // recheck; only selected-source and input-front serial-map lookups are
        // needed for this diagnostic. Do not imply other mappings were read.
        String serialTarget=episodeTouchSourceSerial==0 || selected
          ? episodeSerialTarget(base,game,serialLow,serialHigh,actor)
          : "Episode serial map unrelatedSource=not_inspected\n";
        result.append(serialTarget);
        if(episodeTouchSourceSerial!=0 && selected) {
          if(!serialTarget.endsWith("sameSource=yes"+System.lineSeparator())) throw new IllegalStateException("Selected Episode source serial-map identity mismatch");
          result.append(String.format("Episode selected source serial=%08x%08x ref=%s group=%s livingCamp0Hunter=true actualDOWNTarget=unproved%n",
            serialHigh,serialLow,resId,groupId));
        }
        boolean detailSelected=!episodeTouchOnly || (camp==0 && selected);
        if((episodeSkillsOnly && detailSelected)||episodeExchangeOnly) result.append(episodeActorStateSnapshot(base,actor));
        if(episodeSkillsOnly && detailSelected) {
          result.append(episodeCombatScalarSnapshot(base,actor));
          // Touch-time admission does not need the complete registered aura
          // and recipient-buff corpus. Keep those in paused --episode-skills.
          if(!episodeTouchOnly) {
            result.append(episodeSkillRegistrationSnapshot(base,actor));
            result.append(episodeRecipientBuffSnapshot(base,actor));
          }
        }
        if(episodeExchangeOnly && camp==0) result.append(episodeSpineCaptureSnapshot(base,actor,component,componentControl));
        if(episodeSkillsOnly && camp==0 && selected && actorVptr==base+0x214a3fcL)
          result.append(episodeSkillSnapshot(base,actor));
        if(u32(member+8)!=actor || u32(member+0xc)!=actorControl || u32(actor)!=actorVptr ||
           u32(actorControl)!=actorControlVptr || (int)u32(actorControl+4)<0 ||
           !cppString(actor+0x888).equals(resId) || !cppString(actor+0x898).equals(groupId) ||
           u32(actor+0x880)!=serialLow || u32(actor+0x884)!=serialHigh ||
           f32(actor+0x8b0)!=hp || u32(actor+0xa28)!=component || u32(actor+0xa2c)!=componentControl ||
           (episodeTouchSourceSerial!=0 && selected && u32(actor+0x988)!=0) ||
           (component!=0 && (u32(component)!=componentVptr || u32(componentControl)!=componentControlVptr || (int)u32(componentControl+4)<0)))
          throw new IllegalStateException("Episode actor material ownership changed");
        member=u32(member+4);
      }
      if(member!=sentinel || u32(group+0x280)!=memberFirst || u32(node+0x14)!=group || u32(node+0x18)!=groupControl ||
         u32(group)!=base+0x2149f68L || u32(groupControl)!=groupControlVptr || (int)u32(groupControl+4)<0 ||
         u32(group+0x2d0)!=camp || f32(group+0x2bc)!=sp || f32(group+0x2c0)!=rate || f32(group+0x2c4)!=maxSP)
        throw new IllegalStateException("Episode group ownership/list changed or exceeds16");
      node=u32(node);
    }
    if(node!=0 || groups.size()!=count || u32(game+0x33c)!=first || u32(game+0x340)!=count)
      throw new IllegalStateException("Episode material map changed");
    if(episodeTouchSourceSerial!=0 && selectedSources!=1)
      throw new IllegalStateException("Selected Episode source absent or duplicated in current groups");
    result.append("Episode material limits: group shared-control allocation type has repeated pair/nonexpired checks only; actor/body emplace owners verified; "+
      (episodeExchangeOnly?"exchange body/UI diagnostics do not authorize capture/drop input.\n":
       episodeSkillsOnly?"skill diagnostic ancestor attachment/physical conversion unproved.\n":"no internal component attachment reads.\n"));
    return result.toString();
  }
  static String episodeSkillRegistrationSnapshot(long base,long actor) throws Exception {
    // OnInit moves a typed SkillMgr shared pair to 9a8/9ac. Its recovered
    // emplace owns a 0x70-byte manager at control+0x10 (allocation0x80).
    long manager=u32(actor+0x9a8),control=u32(actor+0x9ac);
    if(manager==0 || control==0 || manager!=control+0x10 || u32(manager)!=base+0x214a710L ||
       u32(control)!=base+0x21495e0L || (int)u32(control+4)<0)
      throw new IllegalStateException("Episode skill manager emplace owner unproved");
    long count=u32(manager+0x50),begin=u32(actor+0x9cc),end=u32(actor+0x9d0),capacity=u32(actor+0x9d4);
    if(count>64 || ((begin|end|capacity)&3)!=0 || end<begin || capacity<end || (end-begin)%0xe8!=0 || (capacity-begin)%0xe8!=0 ||
       (capacity-begin)/0xe8>64 || (begin==0 && (end!=0 || capacity!=0)))
      throw new IllegalStateException("Episode registered skill/aura bounds invalid");
    List<long[]> serials=new ArrayList<>();List<String> labels=new ArrayList<>();
    List<byte[]> prefixes=new ArrayList<>();List<String> payloads=new ArrayList<>();
    for(long row=begin;row<end;row+=0xe8) {
      memory(row,0xe8); // Typed AURA vector extent, not a polymorphic object.
      long low=u32(row+0xe0),high=u32(row+0xe4);
      serials.add(new long[]{row,low,high});labels.add(String.format("%08x%08x",high,low));
      byte[] prefix=memory(row,0x34);prefixes.add(prefix);
      ByteBuffer fields=ByteBuffer.wrap(prefix).order(ByteOrder.LITTLE_ENDIAN);
      for(int offset=0x18;offset<0x30;offset+=4) if(!Float.isFinite(fields.getFloat(offset)))
        throw new IllegalStateException("Episode aura numeric prefix nonfinite");
      payloads.add(String.format(Locale.ROOT,
        "auraId=%08x%08x definitionSerial=%d targetType=%d targetStat=%d referStat=%d referType=%d effectType=%d delay=%.6f coefficient=%.6f coefficientUp=%.6f durationSeconds=%.6f durationUpSeconds=%.6f intervalSeconds=%.6f rawInteger30=%d",
        high,low,Integer.toUnsignedLong(fields.getInt(0)),fields.getInt(4),fields.getInt(8),fields.getInt(0xc),fields.getInt(0x10),fields.getInt(0x14),
        fields.getFloat(0x18),fields.getFloat(0x1c),fields.getFloat(0x20),fields.getFloat(0x24),fields.getFloat(0x28),fields.getFloat(0x2c),fields.getInt(0x30)));
    }
    for(long[] row:serials) if(u32(row[0]+0xe0)!=row[1] || u32(row[0]+0xe4)!=row[2])
      throw new IllegalStateException("Episode aura serial changed");
    for(int i=0;i<serials.size();i++) if(!Arrays.equals(prefixes.get(i),memory(serials.get(i)[0],0x34)))
      throw new IllegalStateException("Episode aura numeric prefix changed");
    if(u32(actor+0x9a8)!=manager || u32(actor+0x9ac)!=control || u32(manager)!=base+0x214a710L ||
       u32(control)!=base+0x21495e0L || (int)u32(control+4)<0 || u32(manager+0x50)!=count ||
       u32(actor+0x9cc)!=begin || u32(actor+0x9d0)!=end || u32(actor+0x9d4)!=capacity)
      throw new IllegalStateException("Episode skill registration snapshot changed");
    return String.format("Episode skill registration managerOwner=emplace_verified registeredItems=%d auraCount=%d auraSerials=%s skillTypes=unproved application=unproved%n",
      count,(end-begin)/0xe8,labels)+String.join("\n",payloads)+(payloads.isEmpty()?"":"\n");
  }
  static String episodeRecipientBuffSnapshot(long base,long actor) throws Exception {
    long buff=u32(actor+0x9b0),control=u32(actor+0x9b4);
    if(buff==0 || control==0 || buff!=control+0x10 || u32(buff)!=base+0x2149d6cL ||
       u32(control)!=base+0x2149608L || (int)u32(control+4)<0)
      throw new IllegalStateException("Episode recipient Buff emplace owner unproved");
    long sentinel=buff+0x98,first=u32(buff+0x9c),last=u32(buff+0x98),count=u32(buff+0xa0),node=first,previous=sentinel;
    if(count>64) throw new IllegalStateException("Episode recipient buff count exceeds bound");
    List<long[]> nodes=new ArrayList<>();List<byte[]> snapshots=new ArrayList<>();Set<Long> seen=new HashSet<>();
    StringBuilder result=new StringBuilder(String.format("Episode recipient actorAddress=%08x buffOwner=emplace_verified buffCount=%d application=unproved%n",actor,count));
    while(node!=sentinel) {
      if(node==0 || (node&3)!=0 || nodes.size()>=count || !seen.add(node) || u32(node)!=previous)
        throw new IllegalStateException("Episode recipient buff list invalid");
      long next=u32(node+4),info=u32(node+8),owner=u32(node+0xc);
      if(info==0 || owner==0 || u32(owner)!=base+0x21499b4L || (int)u32(owner+4)<0 || u32(owner+0xc)!=info)
        throw new IllegalStateException("Episode recipient BuffInfo pool owner unproved");
      byte[] snapshot=memory(info,0x118);ByteBuffer fields=ByteBuffer.wrap(snapshot).order(ByteOrder.LITTLE_ENDIAN);
      for(int offset=0xf0;offset<=0xf8;offset+=4) if(!Float.isFinite(fields.getFloat(offset)))
        throw new IllegalStateException("Episode recipient buff timer/value nonfinite");
      result.append(String.format(Locale.ROOT,
        "Episode recipient buff auraId=%08x%08x sourceSerial=%08x%08x boundSource=%08x boundRecipient=%08x recipientMatches=%s context=%08x active=%08x buffBinding=%08x elapsed=%.6f remaining=%.6f lastValue=%.6f appliedCount=%d targetType=%d targetStat=%d effectType=%d coefficient=%.6f rawInteger30=%d application=unproved%n",
        fields.getInt(0xe4),fields.getInt(0xe0),fields.getInt(0xec),fields.getInt(0xe8),
        Integer.toUnsignedLong(fields.getInt(0x108)),Integer.toUnsignedLong(fields.getInt(0x10c)),Integer.toUnsignedLong(fields.getInt(0x10c))==actor,
        Integer.toUnsignedLong(fields.getInt(0x110)),Integer.toUnsignedLong(fields.getInt(0x100)),Integer.toUnsignedLong(fields.getInt(0x104)),
        fields.getFloat(0xf0),fields.getFloat(0xf4),fields.getFloat(0xf8),Integer.toUnsignedLong(fields.getInt(0xfc)),fields.getInt(4),fields.getInt(8),fields.getInt(0x14),fields.getFloat(0x1c),fields.getInt(0x30)));
      nodes.add(new long[]{node,previous,next,info,owner});snapshots.add(snapshot);previous=node;node=next;
    }
    if(nodes.size()!=count || previous!=last) throw new IllegalStateException("Episode recipient buff count/link mismatch");
    for(int i=0;i<nodes.size();i++) {
      long[] n=nodes.get(i);
      if(u32(n[0])!=n[1] || u32(n[0]+4)!=n[2] || u32(n[0]+8)!=n[3] || u32(n[0]+0xc)!=n[4] ||
         u32(n[4])!=base+0x21499b4L || (int)u32(n[4]+4)<0 || u32(n[4]+0xc)!=n[3] || !Arrays.equals(snapshots.get(i),memory(n[3],0x118)))
        throw new IllegalStateException("Episode recipient buff snapshot changed");
    }
    if(u32(actor+0x9b0)!=buff || u32(actor+0x9b4)!=control || u32(buff)!=base+0x2149d6cL ||
       u32(control)!=base+0x2149608L || (int)u32(control+4)<0 || u32(buff+0x98)!=last || u32(buff+0x9c)!=first || u32(buff+0xa0)!=count)
      throw new IllegalStateException("Episode recipient buff owner/list changed");
    return result.toString();
  }
  static String episodeSpineCaptureSnapshot(long base,long actor,long component,long componentControl) throws Exception {
    if(component==0 || u32(component)!=base+0x2136510L)
      return "Episode capture body=unavailable reason=not_qualified_Spine\n";
    long drawable=u32(component+0x67c),control=u32(component+0x680);
    if(componentControl==0 || component!=componentControl+0x10 || u32(componentControl)!=base+0x21499dcL ||
       (int)u32(componentControl+4)<0 || drawable==0 || control==0 || drawable!=control+0x10 ||
       u32(drawable)!=base+0x2138f30L || u32(control)!=base+0x21353acL || (int)u32(control+4)<0)
      throw new IllegalStateException("Episode Spine body drawable emplace owner unproved");
    if((u32(u32(drawable)+0x90)&~1L)!=base+0x6fc810L || (u32(u32(drawable)+0x94)&~1L)!=base+0x6fb0e0L)
      throw new IllegalStateException("Spine front bound cache consumer unproved");
    byte[] rect=memory(drawable+0x1bc,16),actorFields=memory(actor+0x270,12);
    int flags=memory(drawable+0x60,1)[0]&255;
    ByteBuffer f=ByteBuffer.wrap(rect).order(ByteOrder.LITTLE_ENDIAN);
    float xmin=f.getFloat(),ymin=f.getFloat(),xmax=f.getFloat(),ymax=f.getFloat();
    String ancestry=skillAncestrySnapshot(base,drawable,actor).replace("Episode skill ancestry","Episode body ancestry");
    if(u32(actor+0xa28)!=component || u32(actor+0xa2c)!=componentControl || u32(component)!=base+0x2136510L ||
       u32(componentControl)!=base+0x21499dcL || (int)u32(componentControl+4)<0 || u32(component+0x67c)!=drawable ||
       u32(component+0x680)!=control || u32(drawable)!=base+0x2138f30L || u32(control)!=base+0x21353acL ||
       (int)u32(control+4)<0 || !Arrays.equals(rect,memory(drawable+0x1bc,16)) ||
       !Arrays.equals(actorFields,memory(actor+0x270,12)) || (memory(drawable+0x60,1)[0]&255)!=flags)
      throw new IllegalStateException("Episode capture body snapshot changed");
    boolean finite=Float.isFinite(xmin)&&Float.isFinite(ymin)&&Float.isFinite(xmax)&&Float.isFinite(ymax);
    return String.format("Episode capture body=CMSpineNode_emplace_verified rect=[%f,%f,%f,%f] finite=%s dirty60=%02x hidden270=%d pause278=%x physicalPoint=unavailable%n",
      xmin,ymin,xmax,ymax,finite,flags,actorFields[0]&255,ByteBuffer.wrap(actorFields).order(ByteOrder.LITTLE_ENDIAN).getInt(8))+ancestry+episodeCatchCooldownSnapshot(base,actor);
  }
  static String episodeCatchCooldownSnapshot(long base,long actor) throws Exception {
    long defaults=u32(actor+0x8b4),defaultControl=u32(actor+0x8b8),state=u32(actor+0x8bc),stateControl=u32(actor+0x8c0);
    boolean defaultPool=defaults!=0 && defaultControl!=0 && u32(defaultControl)==base+0x2149d44L &&
      u32(defaultControl+0xc)==defaults;
    boolean defaultInline=defaults!=0 && defaultControl!=0 && defaults==defaultControl+0xc &&
      u32(defaultControl)==base+0x214a854L;
    if((!defaultPool&&!defaultInline) || (int)u32(defaultControl+4)<0) {
      long controlVptr=defaultControl==0?0:u32(defaultControl);
      if(u32(actor+0x8b4)!=defaults || u32(actor+0x8b8)!=defaultControl ||
         (defaultControl!=0 && u32(defaultControl)!=controlVptr))
        throw new IllegalStateException("CanCatch default owner metadata changed");
      return String.format("Episode CanCatch diagnostic=unavailable default_ACTOR_STATE_owner=unproved controlELFvptr=%x objectMinusControl=%d%n",
        controlVptr==0?0:controlVptr-base,defaults-defaultControl);
    }
    if(state==0 || stateControl==0 || u32(stateControl)!=base+0x2149d44L ||
       (int)u32(stateControl+4)<0 || u32(stateControl+0xc)!=state)
      throw new IllegalStateException("CanCatch state owner unproved");
    byte[] defaultsBytes=memory(defaults,0xdc),stateBytes=memory(state,0xdc);
    float defaultCool=ByteBuffer.wrap(defaultsBytes).order(ByteOrder.LITTLE_ENDIAN).getFloat(0x6c);
    float multiplier=ByteBuffer.wrap(stateBytes).order(ByteOrder.LITTLE_ENDIAN).getFloat(0x6c);
    float clock=f32(actor+0x228),lastExchange=f32(actor+0xa58),cool=defaultCool*multiplier;
    long binding=u32(actor+0xa6c);int hidden=memory(actor+0x270,1)[0]&255;
    if(u32(actor+0x8b4)!=defaults || u32(actor+0x8b8)!=defaultControl || u32(actor+0x8bc)!=state ||
       u32(actor+0x8c0)!=stateControl || u32(defaultControl)!=(defaultPool?base+0x2149d44L:base+0x214a854L) ||
       (defaultPool && u32(defaultControl+0xc)!=defaults) || (int)u32(defaultControl+4)<0 ||
       u32(stateControl)!=base+0x2149d44L || (int)u32(stateControl+4)<0 || u32(stateControl+0xc)!=state ||
       !Arrays.equals(defaultsBytes,memory(defaults,0xdc)) || !Arrays.equals(stateBytes,memory(state,0xdc)) ||
       f32(actor+0x228)!=clock || f32(actor+0xa58)!=lastExchange || u32(actor+0xa6c)!=binding ||
       (memory(actor+0x270,1)[0]&255)!=hidden)
      throw new IllegalStateException("CanCatch diagnostic changed");
    boolean finite=Float.isFinite(clock)&&Float.isFinite(lastExchange)&&Float.isFinite(cool);
    return String.format("Episode CanCatch diagnostic=qualified_default_%s_plus_buff_pool clock=%f lastExchange=%f defaultCool=%f multiplier=%f effectiveCool=%f predicate=%s reserveMembership=unproved inputAuthorization=none%n",
      defaultPool?"pool":"emplace",clock,lastExchange,defaultCool,multiplier,cool,!finite?"unproved":Boolean.toString(clock-lastExchange>=cool&&binding!=0&&hidden==0));
  }
  static String episodeExchangeCaughtSnapshot(long base,long game) throws Exception {
    long actor=u32(game+0x198),control=u32(game+0x19c),touchId=u32(game+0x194);
    if(actor==0 && control==0) {
      if(u32(game+0x198)!=0 || u32(game+0x19c)!=0 || u32(game+0x194)!=touchId)
        throw new IllegalStateException("Exchange catch absence changed");
      return "Episode exchange catch=none pairCleared=true\n";
    }
    if(actor==0 || control==0 || actor!=control+0x10 || u32(actor)!=base+0x214a3fcL ||
       u32(control)!=base+0x214bdc4L || (int)u32(control+4)<0 || u32(actor+0x988)!=0)
      throw new IllegalStateException("Exchange caught Hunter owner/camp unproved");
    long low=u32(actor+0x880),high=u32(actor+0x884),state=u32(actor+0xa14);String ref=cppString(actor+0x888);
    String target=episodeSerialTarget(base,game,low,high,actor);
    if(u32(game+0x198)!=actor || u32(game+0x19c)!=control || u32(game+0x194)!=touchId ||
       u32(actor)!=base+0x214a3fcL || u32(control)!=base+0x214bdc4L || (int)u32(control+4)<0 ||
       u32(actor+0x988)!=0 || u32(actor+0x880)!=low || u32(actor+0x884)!=high || u32(actor+0xa14)!=state || !cppString(actor+0x888).equals(ref))
      throw new IllegalStateException("Exchange caught diagnostic changed");
    boolean waiting=state!=8 && ((state-3)&0xffffffffL)>1;
    return String.format("Episode exchange catch=retained serial=%08x%08x resId=%s touchId=%d stateA14=%d IsWaiting=%s cleanup=unproved%n",
      high,low,ref,touchId,state,waiting)+target;
  }
  static String episodeExchangeReserveSnapshot(long base,long game) throws Exception {
    long sentinel=game+0x188,first=u32(game+0x18c),count=u32(game+0x190),node=first;
    if(count>16) throw new IllegalStateException("Exchange reserve list exceeds16");
    Set<Long> seen=new HashSet<>();StringBuilder result=new StringBuilder();
    while(node!=sentinel) {
      if(node==0 || seen.size()>=16 || !seen.add(node)) throw new IllegalStateException("Exchange reserve null/cycle");
      long actor=u32(node+8),control=u32(node+0xc),next=u32(node+4);
      if(actor==0 || control==0 || actor!=control+0x10 || u32(actor)!=base+0x214a3fcL ||
         u32(control)!=base+0x214bdc4L || (int)u32(control+4)<0 || u32(actor+0x988)!=0)
        throw new IllegalStateException("Exchange reserve Hunter owner/camp unproved");
      long low=u32(actor+0x880),high=u32(actor+0x884);String ref=cppString(actor+0x888);
      result.append(String.format("Episode exchange reserve serial=%08x%08x resId=%s membership=airship_list_verified%n",high,low,ref));
      result.append(episodeSerialTarget(base,game,low,high,actor));
      if(u32(node+8)!=actor || u32(node+0xc)!=control || u32(node+4)!=next ||
         u32(actor)!=base+0x214a3fcL || u32(control)!=base+0x214bdc4L || (int)u32(control+4)<0 ||
         u32(actor+0x988)!=0 || u32(actor+0x880)!=low || u32(actor+0x884)!=high || !cppString(actor+0x888).equals(ref))
        throw new IllegalStateException("Exchange reserve member changed");
      node=next;
    }
    if(seen.size()!=count || u32(game+0x18c)!=first || u32(game+0x190)!=count)
      throw new IllegalStateException("Exchange reserve list changed/count mismatch");
    return result.toString();
  }
  static long exchangeObserved(long address,Map<Long,Long> reads) throws Exception {
    long value=u32(address);Long prior=reads.putIfAbsent(address,value);
    if(prior!=null && prior!=value) throw new IllegalStateException("Exchange UI observation changed");
    return value;
  }
  static String exchangeUiName(long base,long object,long control,Map<Long,String> types,
      Map<Long,Long> reads,Map<Long,String> names) throws Exception {
    if(object==0 || control==0 || (int)exchangeObserved(control+4,reads)<0)
      throw new IllegalStateException("Exchange UI strong member unavailable");
    long vptr=exchangeObserved(object,reads);exchangeObserved(control,reads);
    if(!types.containsKey(vptr) || (exchangeObserved(vptr+0x68,reads)&~1L)!=base+0x6c8166L)
      throw new IllegalStateException("Exchange UI unadjusted CMUpdatable base unproved");
    String name=cppString(object+0x258,64);String prior=names.putIfAbsent(object,name);
    if(prior!=null&&!prior.equals(name)) throw new IllegalStateException("Exchange UI name changed");
    return name;
  }
  static long[] exchangeUiChild(long base,long parent,String wanted,Map<Long,String> types,
      Map<Long,Long> reads,Map<Long,String> names) throws Exception {
    long sentinel=parent+0x48,node=exchangeObserved(parent+0x4c,reads),count=exchangeObserved(parent+0x50,reads);
    if(count>64) throw new IllegalStateException("Exchange UI siblings exceed64");
    Set<Long> seen=new HashSet<>();List<String> childNames=new ArrayList<>();long[] found=null;
    while(node!=sentinel) {
      if(node==0 || seen.size()>=64 || !seen.add(node)) throw new IllegalStateException("Exchange UI sibling null/cycle");
      long child=exchangeObserved(node+8,reads),control=exchangeObserved(node+0xc,reads);
      String name=exchangeUiName(base,child,control,types,reads,names);
      childNames.add(name);
      if(name.equals(wanted)) {
        if(found!=null) throw new IllegalStateException("Duplicate exchange UI child");
        found=new long[]{child,control};
      }
      node=exchangeObserved(node+4,reads);
    }
    if(seen.size()!=count || found==null) throw new IllegalStateException("Exchange UI child/count unavailable: "+wanted+
      " parent="+names.get(parent)+" count="+count+" seen="+seen.size()+" children="+childNames);
    return found;
  }
  static String exchangeUiRect(long base,long object,String name,Map<Long,Long> reads) throws Exception {
    long vptr=exchangeObserved(object,reads);
    int flags=(int)exchangeObserved(object+0x60,reads)&255;
    if((exchangeObserved(vptr+0x90,reads)&~1L)!=base+0x6fc810L ||
       (exchangeObserved(vptr+0x94,reads)&~1L)!=base+0x6fb0e0L)
      return "Episode exchange UI name="+name+" rectCache=unavailable consumer=unproved\n";
    float[] rect=new float[4];boolean finite=true;
    for(int i=0;i<4;i++){rect[i]=Float.intBitsToFloat((int)exchangeObserved(object+0x1bc+i*4,reads));finite&=Float.isFinite(rect[i]);}
    return String.format("Episode exchange UI name=%s rect=%s finite=%s dirty60=%02x hidden270=%d allocation=unproved inputAuthorization=none%n",
      name,Arrays.toString(rect),finite,flags,(int)exchangeObserved(object+0x270,reads)&255);
  }
  static String episodeExchangeUiSnapshot(long base,long game) throws Exception {
    Map<Long,Long> reads=new LinkedHashMap<>();Map<Long,String> names=new LinkedHashMap<>(),types=uiTypes(base);
    long root=exchangeObserved(game+0x2c,reads),control=exchangeObserved(game+0x30,reads);
    String name=exchangeUiName(base,root,control,types,reads,names);
    if(!name.equals("SR_INGAME/INGAME_NM")) throw new IllegalStateException("Exchange UI view identity unproved: "+name);
    long[] current={root,control};StringBuilder result=new StringBuilder();
    // OnInit owns CMUIView::GetRoot; its runtime name need not preserve the
    // outer XML VIEWER label. Identify actual named children below that root.
    result.append(exchangeUiRect(base,root,name,reads));
    for(String key:List.of("VIEWER","WAITING_ROOT","BenchCamera","temkdkfk","WAITING","BG_BACK","DOOR_ROOT")) {
      current=exchangeUiChild(base,current[0],key,types,reads,names);
      result.append(exchangeUiRect(base,current[0],key,reads));
    }
    for(String key:List.of("DOOR","IN","OUT")) {
      long[] target=exchangeUiChild(base,current[0],key,types,reads,names);
      result.append(exchangeUiRect(base,target[0],key,reads));
    }
    for(var r:reads.entrySet()) if(u32(r.getKey())!=r.getValue()) throw new IllegalStateException("Exchange UI fields changed");
    for(var n:names.entrySet()) if(!cppString(n.getKey()+0x258,64).equals(n.getValue())) throw new IllegalStateException("Exchange UI final name changed");
    result.append("Episode exchange UI limits: typed shared-node links/repeated base consumers only; concrete child allocation and drop eligibility unproved.\n");
    return result.toString();
  }
  static String episodeControlsSnapshot(long base,long game) throws Exception {
    Map<Long,Long> reads=new LinkedHashMap<>();Map<Long,String> names=new LinkedHashMap<>(),types=uiTypes(base);
    // Episode InitBeforeOpen Gb23cd2 selects FC, not normal UIStage.
    // make_shared G92816e/170/174: control+10, allocationa0.
    long component=exchangeObserved(game+0x20c,reads),componentControl=exchangeObserved(game+0x210,reads);
    if(component==0 || componentControl==0 || (component&3)!=0 || (componentControl&3)!=0 ||
       component!=componentControl+0x10 || exchangeObserved(component,reads)!=base+0x214828cL ||
       exchangeObserved(componentControl,reads)!=base+0x2147030L || (int)exchangeObserved(componentControl+4,reads)<0)
      throw new IllegalStateException("Episode controls exact FC component owner unavailable");
    // FC constructor G951dca retains CMDrawable UI_BATTLE; emplace G952f40.
    long fragment=exchangeObserved(component+0x44,reads),fragmentControl=exchangeObserved(component+0x48,reads);
    if(fragment==0 || fragmentControl==0 || (fragment&3)!=0 || (fragmentControl&3)!=0 ||
       fragment!=fragmentControl+0x10 || exchangeObserved(fragment,reads)!=base+0x2136948L ||
       exchangeObserved(fragmentControl,reads)!=base+0x2136a10L || (int)exchangeObserved(fragmentControl+4,reads)<0)
      throw new IllegalStateException("Episode controls exact UI_BATTLE emplace owner unavailable");
    return episodeControlsUiSnapshot(base,game,fragment,fragmentControl,"UI_BATTLE",reads,names,types);
  }
  /** Match an owned selected fragment to the actual game root by parent pairs
   * and unique child membership, not by concatenating a static XML path. */
  static String episodeControlsUiSnapshot(long base,long game,long fragment,long fragmentControl,String expectedFragmentName,
      Map<Long,Long> reads,Map<Long,String> names,Map<Long,String> types) throws Exception {
    long root=exchangeObserved(game+0x2c,reads),rootControl=exchangeObserved(game+0x30,reads);
    if(!exchangeUiName(base,root,rootControl,types,reads,names).equals("SR_INGAME/INGAME_NM") ||
       !exchangeUiName(base,fragment,fragmentControl,types,reads,names).equals(expectedFragmentName))
      throw new IllegalStateException("Episode controls selected view/fragment name unproved");
    List<long[]> reverse=new ArrayList<>();Set<Long> seen=new HashSet<>();
    long object=fragment,control=fragmentControl;
    while(true) {
      if(reverse.size()>=12 || !seen.add(object))
        throw new IllegalStateException("Episode controls ancestry bound/cycle");
      String name=exchangeUiName(base,object,control,types,reads,names);
      reverse.add(new long[]{object,control});
      if(object==root) {
        if(control!=rootControl)throw new IllegalStateException("Episode controls root owner mismatch");
        break;
      }
      long parent=exchangeObserved(object+0x54,reads),parentControl=exchangeObserved(object+0x58,reads);
      exchangeUiName(base,parent,parentControl,types,reads,names);
      long[] member=exchangeUiChild(base,parent,name,types,reads,names);
      if(member[0]!=object || member[1]!=control)
        throw new IllegalStateException("Episode controls unique parent membership mismatch");
      object=parent;control=parentControl;
    }
    Collections.reverse(reverse);
    List<NativeBattleControls.Visibility> ancestors=new ArrayList<>(),panels=new ArrayList<>();
    StringBuilder result=new StringBuilder();
    for(long[] pair:reverse) {
      var visibility=episodeControlVisibility(pair[0],names.get(pair[0]),reads);
      ancestors.add(visibility);result.append("Episode controls ancestor="+visibility+"\n");
    }
    // CSRFCUITimer retains/attaches BATTLE_ROOT to UI_BATTLE at G956f8c.
    long[] battle=exchangeUiChild(base,fragment,"BATTLE_ROOT",types,reads,names);
    if(exchangeObserved(battle[0]+0x54,reads)!=fragment || exchangeObserved(battle[0]+0x58,reads)!=fragmentControl)
      throw new IllegalStateException("Episode controls BATTLE_ROOT parent mismatch");
    var battleVisibility=episodeControlVisibility(battle[0],"BATTLE_ROOT",reads);
    ancestors.add(battleVisibility);result.append("Episode controls ancestor="+battleVisibility+"\n");
    List<NativeBattleControls.Visibility> lockAncestors=new ArrayList<>(ancestors);
    long[] toggle=exchangeUiChild(base,battle[0],"AUTO_TOGGLE",types,reads,names);
    if(exchangeObserved(toggle[0]+0x54,reads)!=battle[0] || exchangeObserved(toggle[0]+0x58,reads)!=battle[1])
      throw new IllegalStateException("Episode controls toggle parent mismatch");
    var toggleVisibility=episodeControlVisibility(toggle[0],"AUTO_TOGGLE",reads);
    ancestors.add(toggleVisibility);result.append("Episode controls ancestor="+toggleVisibility+"\n");
    for(String key:NativeBattleControls.NORMAL_PANEL_NAMES) {
      long[] panel=exchangeUiChild(base,toggle[0],key,types,reads,names);
      if(exchangeObserved(panel[0]+0x54,reads)!=toggle[0] || exchangeObserved(panel[0]+0x58,reads)!=toggle[1])
        throw new IllegalStateException("Episode controls panel parent mismatch");
      var visibility=episodeControlVisibility(panel[0],key,reads);
      panels.add(visibility);result.append("Episode controls panel="+visibility+"\n");
      if(visibility.effective270()==0)result.append(exchangeUiRect(base,panel[0],key,reads));
    }
    long[] lock=exchangeUiChild(base,battle[0],"AUTO_LOCK",types,reads,names);
    if(exchangeObserved(lock[0]+0x54,reads)!=battle[0] || exchangeObserved(lock[0]+0x58,reads)!=battle[1])
      throw new IllegalStateException("Episode controls lock parent mismatch");
    var lockVisibility=episodeControlVisibility(lock[0],"AUTO_LOCK",reads);
    lockAncestors.add(lockVisibility);result.append("Episode controls lock ancestor="+lockVisibility+"\n");
    long[] lockPanel=exchangeUiChild(base,lock[0],"PA_AUTO_LOCK",types,reads,names);
    if(exchangeObserved(lockPanel[0]+0x54,reads)!=lock[0] || exchangeObserved(lockPanel[0]+0x58,reads)!=lock[1])
      throw new IllegalStateException("Episode controls lock panel parent mismatch");
    var lockPanelVisibility=episodeControlVisibility(lockPanel[0],"PA_AUTO_LOCK",reads);
    result.append("Episode controls lock panel="+lockPanelVisibility+"\n");
    if(lockPanelVisibility.effective270()==0)result.append(exchangeUiRect(base,lockPanel[0],"PA_AUTO_LOCK",reads));
    var mode=NativeBattleControls.classifyQualified(ancestors,panels,lockAncestors,lockPanelVisibility);
    for(var read:reads.entrySet())if(u32(read.getKey())!=read.getValue())
      throw new IllegalStateException("Episode controls owner/path/visibility changed; discard snapshot");
    for(var name:names.entrySet())if(!cppString(name.getKey()+0x258,64).equals(name.getValue()))
      throw new IllegalStateException("Episode controls name changed; discard snapshot");
    result.append("Episode controls mode="+mode+" setting="+
      (mode.setting().isPresent()?Integer.toString(mode.setting().getAsInt()):"unavailable")+
      " currentFragmentOwner=verified parentPairsAndUniqueMembership=verified concreteUiAllocations=unproved nativeGettersCalled=false inputAuthorization=none\n");
    return result.toString();
  }
  static NativeBattleControls.Visibility episodeControlVisibility(long object,String name,Map<Long,Long> reads) throws Exception {
    long hidden=exchangeObserved(object+0x270,reads);
    return new NativeBattleControls.Visibility(name,(int)(hidden&255),(int)((hidden>>>8)&255));
  }
  /** Exact original make_shared<CSRUIImageNode> G7a6d58: object=control+10,
   * primary control213b5cc, primary object213bd20. No generic owner fallback. */
  static void qualifyFeverImageOwner(long base,long object,long control,long vptr,long controlVptr,long strong) {
    if(object==0 || control==0 || (object&3)!=0 || (control&3)!=0 ||
       object!=control+0x10 || vptr!=base+0x213bd20L || controlVptr!=base+0x213b5ccL || (int)strong<0)
      throw new IllegalStateException("Episode fever UIImage emplace owner unproved or expired");
  }
  static String episodeFeverSnapshot(long base,long game) throws Exception {
    Map<Long,Long> reads=new LinkedHashMap<>();Map<Long,String> names=new LinkedHashMap<>(),types=uiTypes(base);
    long root=exchangeObserved(game+0x2c,reads),rootControl=exchangeObserved(game+0x30,reads);
    if(!exchangeUiName(base,root,rootControl,types,reads,names).equals("SR_INGAME/INGAME_NM"))
      throw new IllegalStateException("Episode fever UI root identity unproved");
    long rank=exchangeObserved(game+0x208,reads),phase=exchangeObserved(game+0x2ec,reads);
    long[] parent={root,rootControl};
    for(String key:List.of("VIEWER","MainCamera","RUNNER_ROOT")) {
      long[] child=exchangeUiChild(base,parent[0],key,types,reads,names);
      if(exchangeObserved(child[0]+0x54,reads)!=parent[0] || exchangeObserved(child[0]+0x58,reads)!=parent[1])
        throw new IllegalStateException("Episode fever path parent pair mismatch");
      parent=child;
    }
    StringBuilder result=new StringBuilder(String.format(Locale.ROOT,
      "Episode fever cachedRank208=%d phase2ec=%d rootStrongPair=verified rootConcreteAllocation=unproved nativeGettersCalled=false inputAuthorization=none%n",rank,phase));
    for(String key:List.of("CFE4","CFE3_B")) {
      long[] child=exchangeUiChild(base,parent[0],key,types,reads,names);
      long object=child[0],control=child[1],vptr=exchangeObserved(object,reads),controlVptr=exchangeObserved(control,reads);
      qualifyFeverImageOwner(base,object,control,vptr,controlVptr,exchangeObserved(control+4,reads));
      if(exchangeObserved(object+0x54,reads)!=parent[0] || exchangeObserved(object+0x58,reads)!=parent[1])
        throw new IllegalStateException("Episode fever image parent pair mismatch");
      long hidden=exchangeObserved(object+0x270,reads);
      result.append(String.format(Locale.ROOT,
        "Episode fever image=%s class=CSRUIImageNode owner=emplace_verified hidden270=%d localHidden271=%d resourceDrawing=unproved%n",key,hidden&255,(hidden>>8)&255));
    }
    for(var read:reads.entrySet())if(u32(read.getKey())!=read.getValue())
      throw new IllegalStateException("Episode fever owner/path/fields changed; discard snapshot");
    for(var name:names.entrySet())if(!cppString(name.getKey()+0x258,64).equals(name.getValue()))
      throw new IllegalStateException("Episode fever name changed; discard snapshot");
    return result.toString();
  }
  static String episodeCombatScalarSnapshot(long base,long actor) throws Exception {
    long defaults=u32(actor+0x8b4),defaultControl=u32(actor+0x8b8),state=u32(actor+0x8bc),stateControl=u32(actor+0x8c0);
    boolean pool=defaults!=0 && defaultControl!=0 && u32(defaultControl)==base+0x2149d44L && u32(defaultControl+0xc)==defaults;
    boolean inline=defaults!=0 && defaultControl!=0 && u32(defaultControl)==base+0x214a854L && defaults==defaultControl+0xc;
    if((!pool&&!inline) || (int)u32(defaultControl+4)<0 || state==0 || stateControl==0 ||
       u32(stateControl)!=base+0x2149d44L || (int)u32(stateControl+4)<0 || u32(stateControl+0xc)!=state)
      throw new IllegalStateException("Episode combat scalar owners unproved");
    long defaultVptr=u32(defaultControl),defaultCount=u32(defaultControl+4),stateCount=u32(stateControl+4);
    byte[] original=memory(defaults,0xdc),modified=memory(state,0xdc);
    ByteBuffer d=ByteBuffer.wrap(original).order(ByteOrder.LITTLE_ENDIAN),b=ByteBuffer.wrap(modified).order(ByteOrder.LITTLE_ENDIAN);
    float attack=d.getFloat(0x38),attackMultiplier=b.getFloat(0x38),defense=d.getFloat(0x40),defenseMultiplier=b.getFloat(0x40);
    float skillCost=d.getFloat(0x48),skillCool=d.getFloat(0x4c);
    if(!Float.isFinite(attack) || !Float.isFinite(attackMultiplier) || !Float.isFinite(defense) || !Float.isFinite(defenseMultiplier))
      throw new IllegalStateException("Episode combat scalar nonfinite");
    if(!Float.isFinite(skillCost) || !Float.isFinite(skillCool))
      throw new IllegalStateException("Episode skill cost/cooldown nonfinite");
    // Exact audited float getter arithmetic, reconstructed from typed bytes.
    // No native getter invocation or wire ATK/DEF substitution.
    float reconstructedAttack=Math.max(1f,attack*Math.max(.4f,Math.min(3f,attackMultiplier)));
    float reconstructedDefense=defense*Math.max(.4f,Math.min(3f,defenseMultiplier));
    if(!Float.isFinite(reconstructedAttack) || !Float.isFinite(reconstructedDefense))
      throw new IllegalStateException("Episode reconstructed combat scalar nonfinite");
    if(u32(actor+0x8b4)!=defaults || u32(actor+0x8b8)!=defaultControl || u32(actor+0x8bc)!=state || u32(actor+0x8c0)!=stateControl ||
       u32(defaultControl)!=defaultVptr || u32(defaultControl+4)!=defaultCount ||
       (pool && u32(defaultControl+0xc)!=defaults) || u32(stateControl)!=base+0x2149d44L ||
       u32(stateControl+4)!=stateCount || u32(stateControl+0xc)!=state ||
       !Arrays.equals(original,memory(defaults,0xdc)) || !Arrays.equals(modified,memory(state,0xdc)))
      throw new IllegalStateException("Episode combat scalar snapshot changed");
    return String.format(Locale.ROOT,
      "Episode combat scalars defaultOwner=%s buffOwner=pool_verified defaultAttack38=%.6f attackMultiplier38=%.6f defaultDefense40=%.6f defenseMultiplier40=%.6f reconstructedGetAtk=%.6f reconstructedGetDef=%.6f constructorRank14=%d role80=%d skillCost48=%.6f skillCoolSeconds4c=%.6f nativeGettersCalled=false finalDamage=unproved%n",
      pool?"pool_verified":"emplace_verified",attack,attackMultiplier,defense,defenseMultiplier,reconstructedAttack,reconstructedDefense,Integer.toUnsignedLong(d.getInt(0x14)),Integer.toUnsignedLong(d.getInt(0x80)),skillCost,skillCool);
  }
  static String episodeActorStateSnapshot(long base,long actor) throws Exception {
    // Load/Alloc owns plain ACTOR_STATE (0xdc bytes) through a pool deleter.
    // It has no primary vptr and is NOT inline in its shared control block.
    long state=u32(actor+0x8bc),control=u32(actor+0x8c0);
    if(state==0 && control==0) {
      if(u32(actor+0x8bc)!=0 || u32(actor+0x8c0)!=0)
        throw new IllegalStateException("Episode actor state absence changed");
      return "Episode actor state diagnostic=absent stun=unavailable\n";
    }
    if(state==0 || control==0 || u32(control)!=base+0x2149d44L ||
       (int)u32(control+4)<0 || u32(control+0xc)!=state)
      throw new IllegalStateException("Episode actor state pool owner unproved");
    int strong=(int)u32(control+4);
    byte[] fields=memory(state,0xdc);
    int stun=ByteBuffer.wrap(fields).order(ByteOrder.LITTLE_ENDIAN).getInt(0x94);
    if(u32(actor+0x8bc)!=state || u32(actor+0x8c0)!=control ||
       u32(control)!=base+0x2149d44L || (int)u32(control+4)!=strong ||
       u32(control+0xc)!=state || !Arrays.equals(fields,memory(state,0xdc)))
      throw new IllegalStateException("Episode actor state diagnostic changed");
    ByteBuffer values=ByteBuffer.wrap(fields).order(ByteOrder.LITTLE_ENDIAN);
    String exchange=episodeExchangeOnly ? String.format("Episode exchange state signedStopA0=%d signedCooldownA4=%d CanExchange=unproved%n",
      values.getInt(0xa0),values.getInt(0xa4)):"";
    return String.format("Episode actor state diagnostic=pool_ACTOR_STATE_verified signedStun94=%d stunned=%s matchedInputFront=unproved eligibility=unproved%n",
      stun,stun>0)+exchange;
  }
  static String episodeSkillSnapshot(long base,long actor) throws Exception {
    long icon=u32(actor+0xa6c),control=u32(actor+0xa70);
    int actorEnabled=memory(actor+0xa7d,1)[0]&255;
    if(icon==0 && control==0) {
      if(u32(actor+0xa6c)!=0 || u32(actor+0xa70)!=0 || (memory(actor+0xa7d,1)[0]&255)!=actorEnabled)
        throw new IllegalStateException("Episode skill absence changed");
      return "Episode skill diagnostic=icon_absent\n";
    }
    if(icon==0 || control==0 || icon!=control+0x10 || u32(icon)!=base+0x214db40L ||
       u32(control)!=base+0x2149ac8L || (int)u32(control+4)<0)
      throw new IllegalStateException("Episode skill icon emplace owner unproved");
    int visible=memory(icon+0x6c,1)[0]&255;
    long drawable=u32(icon+0x60),drawableControl=u32(icon+0x64);
    if(drawable==0 || drawableControl==0 || (int)u32(drawableControl+4)<0)
      throw new IllegalStateException("Episode skill drawable strong pair unavailable");
    long drawableVptr=u32(drawable),drawableControlVptr=u32(drawableControl);
    boolean scrollOwner=drawable==drawableControl+0x10 && drawableVptr==base+0x213baccL &&
      drawableControlVptr==base+0x2139540L;
    int drawAlpha=scrollOwner?(memory(drawable+0x1f8,1)[0]&255):-1;
    byte[] hidden=scrollOwner?memory(drawable+0x270,2):null;
    if((u32(drawableVptr+0x90)&~1L)!=base+0x6fc810L ||
       (u32(drawableVptr+0x94)&~1L)!=base+0x6fb0e0L)
      throw new IllegalStateException("Episode skill drawable bound consumer unproved");
    // Diagnostic fields only. The drawable allocation/ancestor chain and
    // physical cursor conversion are NOT established by these slot matches.
    // Never call lazy native getters or turn raw cached bounds into a touch.
    byte[] cached=memory(drawable+0x60,0x16c);
    ByteBuffer fields=ByteBuffer.wrap(cached).order(ByteOrder.LITTLE_ENDIAN);
    int flags=cached[0]&255;
    float local=fields.getFloat(0x54),parent=fields.getFloat(0x58),anim=fields.getFloat(0x5c);
    float xmin=fields.getFloat(0x15c),ymin=fields.getFloat(0x160);
    float xmax=fields.getFloat(0x164),ymax=fields.getFloat(0x168);
    boolean finite=Float.isFinite(local)&&Float.isFinite(parent)&&Float.isFinite(anim)&&
      Float.isFinite(xmin)&&Float.isFinite(ymin)&&Float.isFinite(xmax)&&Float.isFinite(ymax);
    String ancestry=skillAncestrySnapshot(base,drawable,actor);
    String badge=scrollOwner && u32(actor+0x880)==1000005L && u32(actor+0x884)==0 ? episodeHealBadgeSnapshot(base,drawable,drawableControl):"";
    String down="";
    if(episodeTouchOnly) {
      if(observedLogicalDown==null) throw new IllegalStateException("Episode touch requires actual DOWN conversion");
      // Cached geometry and opacity reconstruction only: this observation is
      // before native dispatch, not a report that a callback or skill ran.
      float opacity=(parent*anim)*local;
      boolean qualified=finite && (flags&0x8b)==0 &&
        ancestry.contains("diagnostic=root_reached") && ancestry.contains("containsOwnedActor=true") &&
        ancestry.contains("knownDirtyMasksClear=true") && ancestry.contains("transformMasksClear=true");
      String intersection=qualified?Boolean.toString(observedLogicalDown[0]>=xmin && observedLogicalDown[0]<=xmax &&
        observedLogicalDown[1]>=ymin && observedLogicalDown[1]<=ymax):"unavailable";
      String callbackByte=qualified && Float.isFinite(opacity) && opacity>=0 && opacity<=1 ? Integer.toString((int)(opacity*255.0f)):"unavailable";
      down=String.format(Locale.ROOT,"Episode DOWN diagnostic logicalPoint=%s qualifiedCachedIntersection=%s opacityProduct=%f reconstructedCachedCallbackByte=%s nativeCallbackDelivery=unproved pendingSkill=see_inline_scene_reserve_diagnostic backgroundPause8=see_background_diagnostic oppositeFrontViewport=unproved%n",
        Arrays.toString(observedLogicalDown),intersection,opacity,callbackByte);
    }
    if(u32(actor+0xa6c)!=icon || u32(actor+0xa70)!=control || u32(icon)!=base+0x214db40L ||
       u32(control)!=base+0x2149ac8L || (int)u32(control+4)<0 ||
       (memory(actor+0xa7d,1)[0]&255)!=actorEnabled || (memory(icon+0x6c,1)[0]&255)!=visible ||
       u32(icon+0x60)!=drawable || u32(icon+0x64)!=drawableControl || u32(drawable)!=drawableVptr ||
       u32(drawableControl)!=drawableControlVptr || (int)u32(drawableControl+4)<0 ||
       (scrollOwner && ((memory(drawable+0x1f8,1)[0]&255)!=drawAlpha || !Arrays.equals(hidden,memory(drawable+0x270,2)))) ||
       !Arrays.equals(cached,memory(drawable+0x60,0x16c)))
      throw new IllegalStateException("Episode skill diagnostic snapshot changed");
    return String.format("Episode skill diagnostic=raw_cache_only actorEnabled=%d iconVisible=%d dirty60=%02x finite=%s localCacheClean=%s rect=[%f,%f,%f,%f] opacityFactors=[%f,%f,%f] drawableELFvptr=%x drawableControlELFvptr=%x drawableAllocation=%s ancestors=unproved physicalPoint=unavailable eligibility=unproved%n",
      actorEnabled,visible,flags,finite,(flags&0x8b)==0,xmin,ymin,xmax,ymax,local,parent,anim,
      drawableVptr-base,drawableControlVptr-base,scrollOwner?"CSRUIScrollView_emplace_verified":"unproved")+
      String.format("Episode skill draw diagnostic drawAlpha1f8=%s effectiveHidden270=%s localHidden271=%s renderedChildren=unproved%n",
        scrollOwner?Integer.toString(drawAlpha):"unavailable",scrollOwner?Integer.toString(hidden[0]&255):"unavailable",
        scrollOwner?Integer.toString(hidden[1]&255):"unavailable")+ancestry+badge+down;
  }
  static String episodeHealBadgeSnapshot(long base,long root,long rootControl) throws Exception {
    Map<Long,Long> reads=new LinkedHashMap<>();Map<Long,String> names=new LinkedHashMap<>(),types=uiTypes(base);
    if(!exchangeUiName(base,root,rootControl,types,reads,names).equals("SKILL_ICON"))
      throw new IllegalStateException("Heal badge root identity unproved");
    long[] background=exchangeUiChild(base,root,"BACK_GROUND",types,reads,names);
    long[] icon=exchangeUiChild(base,background[0],"ICON",types,reads,names);
    StringBuilder result=new StringBuilder();
    for(long[] row:new long[][]{{background[0],background[1],root,rootControl},{icon[0],icon[1],background[0],background[1]}}) {
      long object=row[0],control=row[1],vptr=exchangeObserved(object,reads),cv=exchangeObserved(control,reads);
      boolean drawable=vptr==base+0x2136948L && cv==base+0x2136468L && exchangeObserved(control+0xc,reads)==object;
      boolean rect=vptr==base+0x213b7fcL && cv==base+0x213b8c4L && object==control+0x10;
      boolean image=vptr==base+0x2136f20L && cv==base+0x2136118L && object==control+0x10;
      if(!drawable && !rect && !image) throw new IllegalStateException(String.format("Heal badge concrete child owner unproved: %s class=%s vptrELF=%x controlELF=%x objectMinusControl=%x",names.get(object),types.get(vptr),vptr-base,cv-base,object-control));
      if(exchangeObserved(object+0x54,reads)!=row[2] || exchangeObserved(object+0x58,reads)!=row[3])
        throw new IllegalStateException("Heal badge child parent mismatch");
      long draw=exchangeObserved(vptr+0xc,reads)&~1L,onDraw=exchangeObserved(vptr+0x2c,reads)&~1L;
      if(draw!=base+0x6fb7f8L || (image && onDraw!=base+0x7074b4L) || (rect && onDraw!=base+0x798694L))
        throw new IllegalStateException("Heal badge draw consumer unproved");
      long visibility=exchangeObserved(object+0x270,reads),alpha=exchangeObserved(object+0x1f8,reads);
      float b4=Float.intBitsToFloat((int)exchangeObserved(object+0xb4,reads));
      float b8=Float.intBitsToFloat((int)exchangeObserved(object+0xb8,reads));
      float bc=Float.intBitsToFloat((int)exchangeObserved(object+0xbc,reads));
      if(!Float.isFinite(b4)||!Float.isFinite(b8)||!Float.isFinite(bc)) throw new IllegalStateException("Heal badge opacity nonfinite");
      result.append(String.format(Locale.ROOT,"Episode heal badge name=%s allocation=%s effectiveHidden270=%d localHidden271=%d drawAlpha1f8=%d rawOpacityFactors=[%f,%f,%f] drawELF=%x onDrawELF=%x resourceDrawing=unproved%n",
        names.get(object),drawable?"CMDrawable_separate_verified":rect?"CSRUIRect_emplace_verified":"CMImageNode_emplace_verified",visibility&255,(visibility>>8)&255,alpha&255,b4,b8,bc,draw-base,onDraw-base));
    }
    for(var read:reads.entrySet()) if(u32(read.getKey())!=read.getValue()) throw new IllegalStateException("Heal badge graph or values changed");
    for(var name:names.entrySet()) if(!cppString(name.getKey()+0x258,96).equals(name.getValue())) throw new IllegalStateException("Heal badge name changed");
    return result.toString();
  }
  static String episodeHealSourceSnapshot(long base,long game) throws Exception {
    return episodeHealSourceSnapshot(base,game,new HealSourceSelection("C004",1000005L));
  }
  static String episodeHealSourceSnapshot(long base,long game,HealSourceSelection selection) throws Exception {
    Map<Long,Long> reads=new LinkedHashMap<>();Set<Long> visited=new HashSet<>();
    long node=exchangeObserved(game+0x400,reads),count=exchangeObserved(game+0x404,reads);
    if(count>32) throw new IllegalStateException("Heal source map exceeds32");
    long actor=0,control=0;
    while(node!=0) {
      if(visited.size()>=32 || !visited.add(node)) throw new IllegalStateException("Heal source map depth/cycle");
      long low=exchangeObserved(node+0x10,reads),high=exchangeObserved(node+0x14,reads);
      int comparison=Long.compare(0,high);if(comparison==0)comparison=Long.compare(selection.serial(),low);
      if(comparison==0) {actor=exchangeObserved(node+0x18,reads);control=exchangeObserved(node+0x1c,reads);break;}
      node=exchangeObserved(node+(comparison<0?0:4),reads);
    }
    if(actor==0 || control==0 || actor!=control+0x10 || exchangeObserved(actor,reads)!=base+0x214a3fcL ||
       exchangeObserved(control,reads)!=base+0x214bdc4L || (int)exchangeObserved(control+4,reads)<0 ||
       exchangeObserved(actor+0x880,reads)!=selection.serial() || exchangeObserved(actor+0x884,reads)!=0 || exchangeObserved(actor+0x988,reads)!=0)
      throw new IllegalStateException("Heal source living camp0 Hunter owner unproved");
    float hp=Float.intBitsToFloat((int)exchangeObserved(actor+0x8b0,reads));String ref=cppString(actor+0x888);
    if(!Float.isFinite(hp) || hp<=0 || !ref.equals(selection.ref())) throw new IllegalStateException("Heal source absent/dead/ref mismatch");
    String result=String.format("Episode heal source serial=%d ref=%s hp=%f selection=exact_serial_map concreteHunterOwner=verified inputAuthorization=none%n",selection.serial(),ref,hp)+episodeHealGroupRageSnapshot(base,game,actor,control)+episodeSkillSnapshot(base,actor);
    for(var read:reads.entrySet()) if(u32(read.getKey())!=read.getValue()) throw new IllegalStateException("Heal source map/actor changed");
    if(!cppString(actor+0x888).equals(ref))throw new IllegalStateException("Heal source ref changed");
    return result;
  }
  static String episodeHealGroupRageSnapshot(long base,long game,long source,long sourceControl) throws Exception {
    Map<Long,Long> reads=new LinkedHashMap<>();Set<Long> groups=new HashSet<>();int matches=0;
    long node=exchangeObserved(game+0x33c,reads),count=exchangeObserved(game+0x340,reads);
    if(count>8) throw new IllegalStateException("Heal source group count exceeds8");
    String result="";
    while(node!=0) {
      if(groups.size()>=8 || !groups.add(node)) throw new IllegalStateException("Heal source group bound/cycle");
      long group=exchangeObserved(node+0x14,reads),control=exchangeObserved(node+0x18,reads);
      if(group==0 || control==0 || exchangeObserved(group,reads)!=base+0x2149f68L || (int)exchangeObserved(control+4,reads)<0)
        throw new IllegalStateException("Heal source group identity/pair unavailable");
      exchangeObserved(control,reads);
      long camp=exchangeObserved(group+0x2d0,reads),sentinel=group+0x27c,member=exchangeObserved(group+0x280,reads);
      if(camp>1) throw new IllegalStateException("Heal source group camp invalid");
      Set<Long> members=new HashSet<>();boolean contains=false;
      while(member!=sentinel) {
        if(member==0 || members.size()>=16 || !members.add(member)) throw new IllegalStateException("Heal source member bound/cycle");
        long actor=exchangeObserved(member+8,reads),actorControl=exchangeObserved(member+0xc,reads);
        if(actor==source || actorControl==sourceControl) {
          if(actor!=source || actorControl!=sourceControl || camp!=0 || contains) throw new IllegalStateException("Heal source member pair/camp mismatch");
          contains=true;matches++;
        }
        member=exchangeObserved(member+4,reads);
      }
      if(contains) {
        float sp=Float.intBitsToFloat((int)exchangeObserved(group+0x2bc,reads));
        float max=Float.intBitsToFloat((int)exchangeObserved(group+0x2c4,reads));
        if(!Float.isFinite(sp)||!Float.isFinite(max)||sp<0||max<0) throw new IllegalStateException("Heal source Rage invalid");
        result=String.format(Locale.ROOT,"Episode heal group camp=0 SP=%f maxSP=%f membership=unique_exact_source_pair GetSkillPoint_offset=2bc groupControlAllocation=unproved nativeAdmission=unproved%n",sp,max);
      }
      node=exchangeObserved(node,reads);
    }
    if(groups.size()!=count || matches!=1) throw new IllegalStateException("Heal source group count/membership mismatch");
    for(var read:reads.entrySet()) if(u32(read.getKey())!=read.getValue()) throw new IllegalStateException("Heal source group/Rage changed");
    return result;
  }
  static String skillAncestrySnapshot(long base,long start,long actor) throws Exception {
    List<long[]> records=new ArrayList<>();Set<Long> visited=new HashSet<>();
    long node=start;String status="depth_bound";boolean containsActor=false,clear=true,transformsClear=true;
    for(int depth=0;depth<12;depth++) {
      if(node==0 || (node&3)!=0 || !visited.add(node)){status="null_alignment_or_cycle";break;}
      long vptr=u32(node),setter=u32(vptr+0x68)&~1L;
      if(setter!=base+0x6c8166L){status="unproved_base_slot";break;}
      long parent=u32(node+0x54),control=u32(node+0x58);int flags=memory(node+0x60,1)[0]&255;
      containsActor|=node==actor;clear&=(flags&0x8b)==0;
      transformsClear&=(flags&3)==0;
      long controlVptr=control==0?0:u32(control);
      int strong=control==0?0:(int)u32(control+4);
      byte[] visibility=memory(node+0x270,2);
      records.add(new long[]{node,vptr,parent,control,controlVptr,strong,flags,visibility[0]&255,visibility[1]&255});
      if(parent==0 && control==0){status="root_reached";break;}
      if(parent==0 || control==0 || strong<0){status="weak_parent_unavailable";break;}
      node=parent;
    }
    List<String> path=new ArrayList<>(),hiddenPath=new ArrayList<>();
    for(long[] r:records) {
      if(u32(r[0])!=r[1] || (u32(r[1]+0x68)&~1L)!=base+0x6c8166L || u32(r[0]+0x54)!=r[2] ||
         u32(r[0]+0x58)!=r[3] || (memory(r[0]+0x60,1)[0]&255)!=r[6] ||
         (memory(r[0]+0x270,1)[0]&255)!=r[7] || (memory(r[0]+0x271,1)[0]&255)!=r[8] ||
         (r[3]!=0&&(u32(r[3])!=r[4]||(int)u32(r[3]+4)!=r[5])))
        throw new IllegalStateException("Skill ancestry diagnostic changed");
      path.add(String.format("%x:%02x",r[1]-base,r[6]));
      hiddenPath.add(String.format("%x:%d/%d",r[1]-base,r[7],r[8]));
    }
    return String.format("Episode skill ancestry diagnostic=%s depth=%d containsOwnedActor=%s knownDirtyMasksClear=%s transformMasksClear=%s pathELFvptrFlags=%s pathEffectiveLocalHidden=%s weakPairs=rechecked concreteAllocations=unproved inputAuthorization=none%n",
      status,records.size(),containsActor,clear,transformsClear,path,hiddenPath);
  }
  static String episodeSerialTarget(long base,long game,long low,long high,long source) throws Exception {
    long root=u32(game+0x400),count=u32(game+0x404),node=root;
    if(count>32) throw new IllegalStateException("Episode serial map exceeds32");
    Set<Long> visited=new HashSet<>();String result="Episode serial map target=absent\n";
    while(node!=0 && visited.size()<32) {
      if(!visited.add(node)) throw new IllegalStateException("Episode serial map cycle");
      long nodeLow=u32(node+0x10),nodeHigh=u32(node+0x14);
      int compare=Long.compare(high,nodeHigh);if(compare==0) compare=Long.compare(low,nodeLow);
      if(compare==0) {
        long actor=u32(node+0x18),control=u32(node+0x1c);
        long actorVptr=actor==0?0:u32(actor),controlVptr=control==0?0:u32(control);
        // Same two concrete emplace pairs verified in the owned group walk.
        if(actor==0 || control==0 || actor!=control+0x10 || (int)u32(control+4)<0 ||
          !((actorVptr==base+0x214a3fcL && controlVptr==base+0x214bdc4L) ||
            (actorVptr==base+0x214a638L && controlVptr==base+0x214bd9cL)))
          throw new IllegalStateException("Episode serial map actor emplace owner unproved");
        String resId=cppString(actor+0x888);long camp=u32(actor+0x988);
        if(camp>1 || u32(actor+0x880)!=low || u32(actor+0x884)!=high || u32(node+0x18)!=actor ||
          u32(node+0x1c)!=control || u32(actor)!=actorVptr || u32(control)!=controlVptr || (int)u32(control+4)<0 ||
          !cppString(actor+0x888).equals(resId) || u32(actor+0x988)!=camp)
          throw new IllegalStateException("Episode serial map target changed");
        result=String.format("Episode serial map targetResId=%s camp=%d sameSource=%s%n",resId,camp,actor==source?"yes":"no");
        break;
      }
      node=u32(node+(compare<0?0:4));
    }
    if((node!=0 && visited.size()==32) || u32(game+0x400)!=root || u32(game+0x404)!=count)
      throw new IllegalStateException("Episode serial map changed or depth exceeded");
    return result;
  }
  static void inspectFishingHook(long base) throws Exception {
    // Original read-only ELF .dynsym: _ZTV28CSRSceneTutorialMFishingHook=2177cb0;
    // Control _ZTVNSt6__ndk120__shared_ptr_pointerIP28CSRSceneTutorialMFishingHookNS_14default_deleteIS1_EENS_9allocatorIS1_EEEE
    // =217510c. Both guards use original primary table+8, not Ghidra image bias.
    // Pending live diagnostic: current-scene only; never guesses a modal fallback.
    long app=u32(base+0x21ef1e0L);
    if(app==0) throw new IllegalStateException("Fishing hook app unavailable");
    long manager=u32(app+8);
    if(manager==0 || u32(manager)!=base+0x21735a4L)
      throw new IllegalStateException("unexpected fishing hook scene manager");
    long scene=u32(manager+0x34),control=u32(manager+0x38);
    if(scene==0 || control==0 || u32(scene)!=base+0x2177cb8L ||
       u32(control)!=base+0x2175114L || (int)u32(control+4)<0 || u32(control+0xc)!=scene)
      throw new IllegalStateException("current scene is not owned TutorialMFishingHook; no hook reads");
    int[] offsets={0x658,0x65c,0x6a0,0x6a4,0x6a8,0x6ac,0x664,0x668,0x78c,0x798};
    long[] values=new long[offsets.length];
    for(int i=0;i<offsets.length;i++) values[i]=u32(scene+offsets[i]);
    int phase=memory(scene+0x7c8,1)[0]&255,input=memory(scene+0x7c9,1)[0]&255;
    float[] floats=new float[offsets.length];
    for(int i=0;i<offsets.length;i++) {
      if(i==1 || i==9) continue;
      floats[i]=Float.intBitsToFloat((int)values[i]);
      if(!Float.isFinite(floats[i])) throw new IllegalStateException("nonfinite fishing hook field; discard snapshot");
    }
    if(u32(base+0x21ef1e0L)!=app || u32(app+8)!=manager || u32(manager)!=base+0x21735a4L ||
       u32(manager+0x34)!=scene || u32(manager+0x38)!=control || u32(scene)!=base+0x2177cb8L ||
       u32(control)!=base+0x2175114L || (int)u32(control+4)<0 || u32(control+0xc)!=scene)
      throw new IllegalStateException("fishing hook ownership changed; discard snapshot");
    for(int i=0;i<offsets.length;i++) if(u32(scene+offsets[i])!=values[i])
      throw new IllegalStateException("fishing hook field changed; discard snapshot");
    if((memory(scene+0x7c8,1)[0]&255)!=phase || (memory(scene+0x7c9,1)[0]&255)!=input ||
       u32(base+0x21ef1e0L)!=app || u32(app+8)!=manager || u32(manager)!=base+0x21735a4L ||
       u32(manager+0x34)!=scene || u32(manager+0x38)!=control || u32(scene)!=base+0x2177cb8L ||
       u32(control)!=base+0x2175114L || (int)u32(control+4)<0 || u32(control+0xc)!=scene)
      throw new IllegalStateException("fishing hook fields/owner changed; discard snapshot");
    System.out.printf("Fishing hook sceneELFvptr=2177cb8 gauge658=%f mode65c=%d " +
      "decay6a0=%f decay6a4=%f increment6a8=%f increment6ac=%f " +
      "timer664=%f timer668=%f cooldown78c=%f direction798=%d phase7c8=%d input7c9=%d%n",
      floats[0],(int)values[1],floats[2],floats[3],floats[4],floats[5],
      floats[6],floats[7],floats[8],(int)values[9],phase,input);
  }
  static long u64(long address) throws Exception {
    long value=ByteBuffer.wrap(memory(address,8)).order(ByteOrder.LITTLE_ENDIAN).getLong();
    if(value<0 || value>9007199254740991L) throw new IllegalStateException("instance ID outside local safe range");
    return value;
  }
  static void inspectGymSources(long base) throws Exception {
    long app=u32(base+0x21ef1e0L),manager=u32(app+8);
    if(u32(manager)!=base+0x21735a4L) throw new IllegalStateException("unexpected scene manager");
    long scene=u32(manager+0x34),control=u32(manager+0x38),vptr=u32(scene);
    if(!Set.of(base+0x2176e20L,base+0x218278cL).contains(vptr) || control==0 || (int)u32(control+4)<0)
      throw new IllegalStateException("current scene is not guarded LevelUp/TutorialLevelUp");
    long target=u64(scene+0xd48);
    long cb=u32(scene+0x65c),ce=u32(scene+0x660),cc=u32(scene+0x664);
    long sb=u32(scene+0x668),se=u32(scene+0x66c),sc=u32(scene+0x670);
    long candidates=vectorCount(cb,ce,8),selected=vectorCount(sb,se,8);
    if((cb&7)!=0 || (sb&7)!=0 || ce>cc || se>sc) throw new IllegalStateException("invalid source vector alignment/capacity");
    List<Long> candidateIds=new ArrayList<>(),selectedIds=new ArrayList<>();
    for(int i=0;i<candidates;i++) candidateIds.add(u64(cb+i*8));
    for(int i=0;i<selected;i++) selectedIds.add(u64(sb+i*8));
    if(u32(manager+0x34)!=scene || u32(manager+0x38)!=control || (int)u32(control+4)<0 || u32(scene)!=vptr ||
       u64(scene+0xd48)!=target || u32(scene+0x65c)!=cb || u32(scene+0x660)!=ce || u32(scene+0x664)!=cc ||
       u32(scene+0x668)!=sb || u32(scene+0x66c)!=se || u32(scene+0x670)!=sc)
      throw new IllegalStateException("Gym source selection changed; discard snapshot");
    System.out.printf("Gym scene=%s%n",vptr==base+0x2176e20L ? "TutorialLevelUp" : "TableLevelUp");
    System.out.printf("Gym target=%d candidates=%s selected=%s%n",target,candidateIds,selectedIds);
  }
  static String cppString(long address) throws Exception {
    return cppString(address,16);
  }
  static String cppString(long address,int bound) throws Exception {
    int tag=memory(address,1)[0]&255;
    long length=(tag&1)==0 ? tag>>1 : u32(address+4);
    long data=(tag&1)==0 ? address+1 : u32(address+8);
    if(length>bound) throw new IllegalStateException("string exceeds bounded read");
    return length==0 ? "" : new String(memory(data,(int)length),StandardCharsets.US_ASCII);
  }
  static void inspectGroups(long base,long game) throws Exception {
    long first=u32(game+0x33c),count=u32(game+0x340),node=first;
    if(count>32) throw new IllegalStateException("group map exceeds32-node bound");
    Set<Long> visited=new HashSet<>();StringBuilder result=new StringBuilder();
    for(int i=0;node!=0 && i<32;i++) {
      if(!visited.add(node)) throw new IllegalStateException("group map cycle");
      String key=cppString(node+8);long group=u32(node+0x14);
      if(u32(group)!=base+0x2149f68L) throw new IllegalStateException("unknown group vtable");
      long camp=u32(group+0x2d0);
      float sp=f32(group+0x2bc),rate=f32(group+0x2c0),max=f32(group+0x2c4),clock=f32(group+0x228),delta=f32(group+0x22c);
      if(camp>1 || !Float.isFinite(sp) || !Float.isFinite(rate) || !Float.isFinite(max) ||
         !Float.isFinite(clock) || !Float.isFinite(delta)) throw new IllegalStateException("invalid group fields");
      result.append(String.format("group key=%s camp=%d SP=%f rate=%f maxSP=%f clock=%f delta=%f%n",key,camp,sp,rate,max,clock,delta));
      node=u32(node);
    }
    if(node!=0 || visited.size()!=count || u32(game+0x33c)!=first || u32(game+0x340)!=count)
      throw new IllegalStateException("group map changed or count mismatch; discard snapshot");
    System.out.print(result);
  }
  static long vectorCount(long begin,long end,int stride) {
    long bytes=end-begin;
    if(bytes<0 || bytes%stride!=0 || bytes/stride>32) throw new IllegalStateException("invalid bounded Supply vector");
    return bytes/stride;
  }
  static void inspectCombatTuning(long base) throws Exception {
    long holder=base+0x21d034cL,data=u32(holder),owner=u32(holder+4);
    if(data==0 || owner==0 || u32(owner)!=base+0x21435ccL ||
       (int)u32(owner+4)<0 || u32(owner+0xc)!=data)
      throw new IllegalStateException("unexpected or expired DataMgr owner");
    // LoadLevelData G8b26e4 creates a separate allocation, default-delete
    // control G2153558, pointed to by DataMgr+a850/a854. No primary vptr:
    // CSRLevelData constructor starts with ordinary numeric fields.
    long level=u32(data+0xa850),control=u32(data+0xa854);
    if(level==0 && control==0) {
      if(u32(holder)!=data || u32(holder+4)!=owner || u32(owner)!=base+0x21435ccL || (int)u32(owner+4)<0 ||
         u32(owner+0xc)!=data || u32(data+0xa850)!=0 || u32(data+0xa854)!=0)
        throw new IllegalStateException("empty selected combat tuning changed; discard snapshot");
      System.out.println("selected LevelData unavailable (both registration fields zero); no tuning inferred");
      return;
    }
    long controlVptr=control==0?0:u32(control);
    boolean separate=controlVptr==base+0x2143558L;
    boolean embedded=controlVptr==base+0x2143530L;
    // Original emplace destructor G8b59e8 destroys its object at control+c.
    if(level==0 || control==0 || (!separate && !embedded) ||
       (int)u32(control+4)<0 || (separate ? u32(control+0xc)!=level : level!=control+0xc))
      throw new IllegalStateException(String.format("unexpected or expired selected LevelData owner: pointer=%x control=%x controlVptrElf=%x",level,control,control==0?0:u32(control)-base));
    float bonus=f32(level+0x254);
    if(!Float.isFinite(bonus) || bonus<=0)
      throw new IllegalStateException("invalid selected attack speed bonus");
    if(u32(holder)!=data || u32(holder+4)!=owner || u32(owner)!=base+0x21435ccL || (int)u32(owner+4)<0 ||
       u32(owner+0xc)!=data || u32(data+0xa850)!=level || u32(data+0xa854)!=control ||
       u32(control)!=controlVptr || (int)u32(control+4)<0 ||
       (separate ? u32(control+0xc)!=level : level!=control+0xc) || f32(level+0x254)!=bonus)
      throw new IllegalStateException("selected combat tuning changed; discard snapshot");
    System.out.printf("selected LevelData=%x control=%x atk_spd_bonus=%f (current registration; scene association not inferred)%n",level,control,bonus);
  }
  static void inspectSupply(long base) throws Exception {
    // Ghidra root21e034c, controlvptr21535cc; subtract image bias10000.
    long holder=base+0x21d034cL,data=u32(holder),control=u32(holder+4);
    if(data==0 || control==0 || u32(control)!=base+0x21435ccL || (int)u32(control+4)<0 || u32(control+0xc)!=data)
      throw new IllegalStateException("unexpected or expired DataMgr owner");
    long level=u32(data+0xa858),ref=u32(level),play=u32(level+8);
    long rb=u32(ref+0x2c0),re=u32(ref+0x2c4),ib=u32(play+0x318),ie=u32(play+0x31c);
    long refs=vectorCount(rb,re,0x58),instances=vectorCount(ib,ie,0x10);
    StringBuilder result=new StringBuilder(String.format("Supply reference count=%d instance count=%d%n",refs,instances));
    for(int i=0;i<refs;i++) {
      long row=rb+i*0x58;
      result.append(String.format("Supply reference id=%s start=%s end=%s AP=%d%n",cppString(row),cppString(row+0xc),cppString(row+0x18),u32(row+0x24)));
    }
    for(int i=0;i<instances;i++) {
      long row=ib+i*0x10;
      result.append(String.format("Supply instance id=%s status=%d%n",cppString(row),u32(row+0xc)));
    }
    if(u32(holder)!=data || u32(holder+4)!=control || (int)u32(control+4)<0 || u32(control+0xc)!=data ||
       u32(data+0xa858)!=level || u32(level)!=ref || u32(level+8)!=play ||
       u32(ref+0x2c0)!=rb || u32(ref+0x2c4)!=re || u32(play+0x318)!=ib || u32(play+0x31c)!=ie)
      throw new IllegalStateException("Supply registration changed; discard snapshot");
    System.out.print(result);
  }
  static Map<Long,String> uiTypes(long base) throws Exception {
    // DataDump owns recovered evidence; read it without writing/copying the
    // source. A different checkout layout can supply an explicit JVM property.
    String guardPath=System.getProperty("blustone.uiGuards",
      "../Blustone-DataDump/findings/resources/ui-updatable-vptr-guards.json");
    String guards=java.nio.file.Files.readString(java.nio.file.Path.of(guardPath));
    if(guards.length()>65536) throw new IllegalStateException("oversized UI class guards");
    Map<Long,String> types=new HashMap<>();
    var matcher=java.util.regex.Pattern.compile("\"0x([0-9a-fA-F]{8})\"\\s*:\\s*\"([^\"\\r\\n]+)\"").matcher(guards);
    while(matcher.find()) types.put(base+Long.parseUnsignedLong(matcher.group(1),16),matcher.group(2));
    if(types.size()!=161) throw new IllegalStateException("unexpected verified UI guard set");
    return types;
  }
  /** Allowlisted marker projection through original initialized ownership only. */
  static void inspectCampaignMarkers(long base) throws Exception {
    long holder=base+0x21d034cL,data=u32(holder),owner=u32(holder+4);
    if(data==0 || owner==0 || u32(owner)!=base+0x21435ccL ||
       (int)u32(owner+4)<0 || u32(owner+0xc)!=data)
      throw new IllegalStateException("unexpected marker DataMgr owner");
    long bridge=u32(data+0xa858);
    if(bridge==0)throw new IllegalStateException("PlayData not initialized; no getter invoked");
    long play=u32(bridge+8),control=u32(bridge+0xc);
    // Original emplace<CSRPlayData> is aligned8: its object starts at control+10.
    if(play==0 || control==0 || u32(control)!=base+0x2143444L ||
       (int)u32(control+4)<0 || play!=control+0x10)
      throw new IllegalStateException("unexpected or expired PlayData marker owner");
    NativeCampaignMarkers projection=new NativeCampaignMarkers(InspectNativeInput::memory);
    Map<String,Object> result=projection.project(play+0x330);
    if(u32(holder)!=data || u32(holder+4)!=owner || u32(owner)!=base+0x21435ccL ||
       (int)u32(owner+4)<0 || u32(owner+0xc)!=data || u32(data+0xa858)!=bridge ||
       u32(bridge+8)!=play || u32(bridge+0xc)!=control || u32(control)!=base+0x2143444L ||
       (int)u32(control+4)<0 || play!=control+0x10)
      throw new IllegalStateException("marker owner changed; discard snapshot");
    projection.verify();
    System.out.println("Allowlisted campaign markers (sample only, reads="+projection.readCount()+"): "+result);
  }

  /** Original result wrapper/child input gates. No getters, marker access or writes. */
  static void inspectResultUi(long base) throws Exception {
    long holder=base+0x21e57f8L, modal=u32(holder), control=u32(holder+4);
    if(modal==0 || control==0 || u32(control)!=base+0x2186a38L ||
       (int)u32(control+4)<0 || u32(control+0xc)!=modal)
      throw new IllegalStateException("unexpected or expired modal owner");
    long app=u32(base+0x21ef1e0L),manager=u32(app+8);
    if(u32(app)!=base+0x2140cb0L || u32(manager)!=base+0x21735a4L)
      throw new IllegalStateException("unexpected app/scene router");
    long scene=u32(manager+0x34),sceneControl=u32(manager+0x38),sceneVptr=scene==0?0:u32(scene);
    if(scene!=0 && (sceneControl==0 || (int)u32(sceneControl+4)<0))
      throw new IllegalStateException("expired router scene");
    int faderEnd=memory(manager+0x673,1)[0]&255,blockDuringFade=memory(manager+0x672,1)[0]&255;
    int sceneEnd=-1;
    if(Set.of(base+0x216f90cL,base+0x2172620L,base+0x216b1c4L).contains(sceneVptr))
      sceneEnd=memory(scene+0x38,1)[0]&255;
    if(faderEnd>1 || blockDuringFade>1 || sceneEnd>1)
      throw new IllegalStateException("invalid router flags");
    long httpHolder=base+0x21ce890L,http=u32(httpHolder),httpControl=u32(httpHolder+4);
    if(http==0 || httpControl==0 || u32(httpControl)!=base+0x213d448L ||
       (int)u32(httpControl+4)<0 || u32(httpControl+0xc)!=http)
      throw new IllegalStateException("unexpected or expired HTTP manager owner");
    long httpProg=u32(http+0x70),postEffectWait=u32(modal+0x6dc);
    if(httpProg>4096 || postEffectWait>4096) throw new IllegalStateException("unbounded modal wait count");
    long primary=u32(modal+0xc),secondary=u32(modal+0x18);
    if(primary>32 || secondary>32) throw new IllegalStateException("modal list exceeds bounded count");
    long count=secondary>0?secondary:primary;
    long back=count>0?u32(modal+(secondary>0?0x10:4)):0;
    long top=count>0?u32(back+8):0, vptr=top!=0?u32(top):0;
    String detail="no recognized result wrapper; no result field reads";
    long child=0,childVptr=0,gate=-1,backGate=-1;
    // Ghidra primary216c124 minus image10000; WIN primary216c3dc likewise.
    if(vptr==base+0x215c124L) {
      gate=memory(top+0xa0,1)[0]&255; backGate=memory(top+0x2c,1)[0]&255;
      if(gate>1 || backGate>1) throw new IllegalStateException("invalid result input flag");
      child=u32(top+0xa4); childVptr=child!=0?u32(child):0;
      if(child!=0 && childVptr!=base+0x215c3dcL)
        throw new IllegalStateException("result child is not guarded WIN class");
      if(child!=0 && (u32(childVptr+0x38)!=base+0xc391e3L ||
                      u32(childVptr+0x40)!=base+0xc39875L))
        throw new IllegalStateException("WIN input virtual slots differ from original");
      detail=String.format("Result wrapper cursor/button gate=%d sceneBackGate=%d WINchild=%s%n",
                          gate,backGate,child!=0);
    }
    if(u32(holder)!=modal || u32(holder+4)!=control || u32(control)!=base+0x2186a38L || (int)u32(control+4)<0 ||
       u32(control+0xc)!=modal || u32(modal+0xc)!=primary || u32(modal+0x18)!=secondary ||
       (count>0 && (u32(modal+(secondary>0?0x10:4))!=back || u32(back+8)!=top || u32(top)!=vptr)) ||
       (gate>=0 && (u32(top+0xa4)!=child || (memory(top+0xa0,1)[0]&255)!=gate ||
                   (memory(top+0x2c,1)[0]&255)!=backGate || (child!=0 && u32(child)!=childVptr))))
      throw new IllegalStateException("result/modal owner changed; discard snapshot");
    if(u32(base+0x21ef1e0L)!=app || u32(app)!=base+0x2140cb0L || u32(app+8)!=manager ||
       u32(manager)!=base+0x21735a4L || u32(manager+0x34)!=scene || u32(manager+0x38)!=sceneControl ||
       (scene!=0 && (u32(scene)!=sceneVptr || (int)u32(sceneControl+4)<0)) ||
       (memory(manager+0x673,1)[0]&255)!=faderEnd || (memory(manager+0x672,1)[0]&255)!=blockDuringFade ||
       (sceneEnd>=0 && (memory(scene+0x38,1)[0]&255)!=sceneEnd) ||
       u32(httpHolder)!=http || u32(httpHolder+4)!=httpControl || u32(httpControl)!=base+0x213d448L ||
       (int)u32(httpControl+4)<0 || u32(httpControl+0xc)!=http ||
       u32(http+0x70)!=httpProg || u32(modal+0x6dc)!=postEffectWait)
      throw new IllegalStateException("touch routing state changed; discard snapshot");
    System.out.printf("Touch route faderEnd=%d blockDuringFade=%d sceneEnd=%d sceneELFvptr=%x HTTPprog=%d postEffectWait=%d%n",
                      faderEnd,blockDuringFade,sceneEnd,sceneVptr==0?0:sceneVptr-base,httpProg,postEffectWait);
    System.out.printf("Result UI modalPrimary=%d modalSecondary=%d topELFvptr=%x%n",
                      primary,secondary,vptr==0?0:vptr-base);
    System.out.println(detail);
  }

  static void inspectGuideState(long base) throws Exception {
    long app=u32(base+0x21ef1e0L),manager=u32(app+8);
    if(u32(manager)!=base+0x21735a4L) throw new IllegalStateException("unexpected scene manager");
    long scene=u32(manager+0x34),sceneControl=u32(manager+0x38),sceneVptr=u32(scene);
    if(sceneControl==0 || (int)u32(sceneControl+4)<0) throw new IllegalStateException("expired current scene");
    long holder=base+0x21e57f8L,modal=u32(holder),control=u32(holder+4);
    if(modal==0 || control==0 || u32(control)!=base+0x2186a38L || (int)u32(control+4)<0 || u32(control+0xc)!=modal)
      throw new IllegalStateException("unexpected or expired modal owner");
    long secondary=u32(modal+0x18),primary=u32(modal+0xc);
    long count=secondary>0?secondary:primary,back=count>0?u32(modal+(secondary>0?0x10:4)):0;
    if(primary>32 || secondary>32) throw new IllegalStateException("modal list exceeds bounded count");
    long top=count>0?u32(back+8):0,topVptr=top>0?u32(top):0;
    String tutorial="";
    long focus=0,focusVptr=0,focusActive=0,focusCallback=0;
    if(topVptr==base+0x21691d4L) { // Original primary _ZTV20CSRPopUpTutorialBase+8.
      focus=u32(top+0xc4);
      if(focus!=0) {
        focusVptr=u32(focus);
        if(focusVptr!=base+0x2185f4cL) throw new IllegalStateException("unexpected tutorial focus class");
        focusActive=u32(focus+0x850); focusCallback=u32(focus+0x8c4);
      }
      tutorial=String.format("Tutorial mode=%d focusPresent=%s activeFocus=%s callbackPresent=%s%n",
        memory(top+0x9c,1)[0]&255,focus!=0,focusActive!=0,focusCallback!=0);
    }
    String village="";
    if(sceneVptr==base+0x216b1c4L)
      village=String.format("Village inputByte=%d tutorial=%x tutorialControl=%x%n",
        memory(scene+0x2c,1)[0]&255,u32(scene+0x928),u32(scene+0x92c));
    if(u32(manager+0x34)!=scene || u32(manager+0x38)!=sceneControl || u32(scene)!=sceneVptr ||
       (int)u32(sceneControl+4)<0 || u32(holder)!=modal || u32(holder+4)!=control ||
       (int)u32(control+4)<0 || u32(control+0xc)!=modal || u32(modal+0x18)!=secondary || u32(modal+0xc)!=primary ||
       (count>0 && (u32(modal+(secondary>0?0x10:4))!=back || u32(back+8)!=top || u32(top)!=topVptr)) ||
       (topVptr==base+0x21691d4L && (u32(top+0xc4)!=focus ||
         (focus!=0 && (u32(focus)!=focusVptr || u32(focus+0x850)!=focusActive || u32(focus+0x8c4)!=focusCallback)))))
      throw new IllegalStateException("scene/modal owner changed; discard snapshot");
    System.out.printf("Guide state sceneELFvptr=%x modalPrimary=%d modalSecondary=%d topELFvptr=%x%n",
      sceneVptr-base,primary,secondary,topVptr==0?0:topVptr-base);
    System.out.print(village);
    System.out.print(tutorial);
    // Unknown top classes are reported by vptr only, never cast/read as a guide.
  }
  /** Read only two fixed clone CDN files through existing app-UID RAF access.
   * Raw bytes stay in private host evidence; no game getter or cache write. */
  static void inspectCdnCurrent(long base) throws Exception {
    if(vm.classesByName("com.vshower.instrumented.InstrumentedActivity").size()!=1)
      throw new IllegalStateException("instrumented identity unavailable");
    long app=u32(base+0x21ef1e0L),manager=u32(app+8);
    if(u32(manager)!=base+0x21735a4L)throw new IllegalStateException("unexpected scene manager");
    long scene=u32(manager+0x34),control=u32(manager+0x38);
    if(u32(scene)!=base+0x216b1c4L || control==0 || (int)u32(control+4)<0)
      throw new IllegalStateException("CDN metadata probe requires live Village");
    // Original get<CPVCDN2> GOT21bba78 -> weak pair21de7fc (Ghidra
    // addresses include +10000). Default Open allocates _CMDefaultDB at
    // shared control+c; its embedded encrypted DB begins at adapter+4.
    long cdn=u32(base+0x21ce7fcL),cdnControl=u32(base+0x21ce800L);
    // Holder7d8c44 allocates a distinct CPVCDN2, then default-delete
    // control (+c = that raw object), vptr G214cc40+8.
    if(cdn==0 || cdnControl==0 || (int)u32(cdnControl+4)<0 ||
       u32(cdnControl)!=base+0x213cc48L || u32(cdnControl+0xc)!=cdn)
      throw new IllegalStateException("CDN singleton is unavailable");
    long adapter=u32(cdn+0x18),adapterControl=u32(cdn+0x1c);
    if(adapter==0 || adapterControl==0 || (int)u32(adapterControl+4)<0 || adapter!=adapterControl+0xc ||
       u32(adapterControl)!=base+0x213739cL || u32(adapter)!=base+0x21373c4L ||
       u32(adapter+4)!=base+0x21881e8L || u32(adapter+8)==0 || memory(adapter+0x18,1)[0]!=0)
      throw new IllegalStateException("CDN default database binding is unproved");
    String namespace=cppString(cdn+0x20,16),database=cppString(adapter+0xc,192);
    long mode=u32(adapter+0x1c);
    long levelDb=u32(adapter+8);
    // DBImpl's MakeRoomForWrite/RecordBackgroundError prove sticky Status
    // pointer at +f0. Report presence only until the Status format is proved.
    if(u32(levelDb)!=base+0x21a6ef4L)
      throw new IllegalStateException("CDN LevelDB implementation type unavailable");
    long backgroundError=u32(levelDb+0xf0);
    byte[] errorState=null;
    int errorCode=0;String errorCategory="none";
    if(backgroundError!=0) {
      // Status constructor/CopyState: uint32 message length, code byte,
      // message bytes. Raw message stays in private host evidence.
      long errorLength=u32(backgroundError);
      if(errorLength>1024)throw new IllegalStateException("CDN error state exceeds bound");
      errorState=memory(backgroundError,(int)errorLength+5);errorCode=errorState[4]&255;
      String errorText=new String(errorState,5,(int)errorLength,StandardCharsets.US_ASCII);
      errorCategory="other";
      for(String category:List.of("No space left on device","Permission denied","No such file or directory",
          "Bad file descriptor","Read-only file system","Input/output error"))
        if(errorText.contains(category))errorCategory=category;
    }
    // Android's /data/user/0 and /data/data names designate this app's
    // directory. Require an exact known clone path, including native trailing /.
    Set<String> clonePaths=Set.of(
      "/data/data/com.vshower.prd_sr.instrumented/files/local/CDN.db",
      "/data/data/com.vshower.prd_sr.instrumented/files/local/CDN.db/",
      "/data/user/0/com.vshower.prd_sr.instrumented/files/local/CDN.db",
      "/data/user/0/com.vshower.prd_sr.instrumented/files/local/CDN.db/");
    if(!namespace.equals("CDN") || mode!=3 ||
       !clonePaths.contains(database)) {
      throw new IllegalStateException("CDN database differs: namespaceCDN="+namespace.equals("CDN")+
        " mode="+mode+" pathLength="+database.length()+" cloneSuffix="+
        database.endsWith("com.vshower.prd_sr.instrumented/files/local/CDN.db"));
    }
    String root=database.endsWith("/")?database:database+"/";
    List<String> cacheFileNames=cdnDirectoryNames(root);
    // Init/constructor use a context wrapper whose +c is the raw shared
    // storage and +10 retains the context allocation. No native operator->.
    long contextRef=u32(cdn+0x34),contextControl=u32(cdn+0x38);
    if(contextRef==0 || contextControl==0 || contextRef!=contextControl+0xc ||
       (int)u32(contextControl+4)<0 || u32(contextControl)!=base+0x213c8d8L)
      throw new IllegalStateException("CDN current context wrapper unavailable");
    long context=u32(contextRef),allocation=u32(contextControl+0x10);
    if(context==0 || allocation==0 || context!=allocation+0x10 || (int)u32(allocation+4)<0)
      throw new IllegalStateException("CDN context allocation unavailable");
    NativeCampaignMarkers headerReader=new NativeCampaignMarkers(InspectNativeInput::memory);
    Map<String,Object> currentHeader=headerReader.projectCdnHeader(context+0x18);
    byte[] current=readCdnFile(root+"CURRENT",64);
    String text=new String(current,StandardCharsets.US_ASCII);
    if(!text.matches("MANIFEST-[0-9]{6,10}\\r?\\n"))
      throw new IllegalStateException("unsupported CDN CURRENT; no contents printed");
    String name=text.strip();
    byte[] manifest=readCdnFile(root+name,524288);
    Map<String,byte[]> copies=new LinkedHashMap<>();
    if(cdnCopySpec!=null) {
      String[] spec=cdnCopySpec.split(":",-1);
      if(spec.length!=2 || !spec[0].equals(name))throw new IllegalStateException("CDN manifest binding changed");
      String[] names=spec[1].split(",",-1);
      if(names.length<1 || names.length>8)throw new IllegalStateException("CDN copy count rejected");
      for(String selected:names) {
        if(!selected.matches("[0-9]{6,10}\\.(ldb|log)") || copies.containsKey(selected))
          throw new IllegalStateException("unsupported CDN filename");
        copies.put(selected,readCdnFile(root+selected,4194304));
      }
      for(var selected:copies.entrySet())if(!Arrays.equals(selected.getValue(),readCdnFile(root+selected.getKey(),4194304)))
        throw new IllegalStateException("CDN selected file changed; discard copy");
    }
    if(!Arrays.equals(current,readCdnFile(root+"CURRENT",64)) ||
       !Arrays.equals(manifest,readCdnFile(root+name,524288)) ||
       u32(manager+0x34)!=scene || u32(manager+0x38)!=control ||
       u32(scene)!=base+0x216b1c4L || (int)u32(control+4)<0 ||
       u32(base+0x21ce7fcL)!=cdn || u32(base+0x21ce800L)!=cdnControl ||
       (int)u32(cdnControl+4)<0 || u32(cdnControl)!=base+0x213cc48L || u32(cdnControl+0xc)!=cdn ||
       u32(cdn+0x18)!=adapter || u32(cdn+0x1c)!=adapterControl ||
       u32(adapterControl)!=base+0x213739cL || (int)u32(adapterControl+4)<0 ||
       u32(adapter)!=base+0x21373c4L || u32(adapter+4)!=base+0x21881e8L ||
       u32(adapter+8)!=levelDb || u32(levelDb)!=base+0x21a6ef4L || u32(levelDb+0xf0)!=backgroundError ||
       memory(adapter+0x18,1)[0]!=0 || u32(adapter+0x1c)!=mode ||
       !cppString(cdn+0x20,16).equals(namespace) || !cppString(adapter+0xc,192).equals(database))
      throw new IllegalStateException("CDN file/scene changed; discard copy");
    if(!cdnDirectoryNames(root).equals(cacheFileNames))
      throw new IllegalStateException("CDN directory inventory changed; discard copy");
    headerReader.verify();
    if(errorState!=null && !Arrays.equals(errorState,memory(backgroundError,errorState.length)))
      throw new IllegalStateException("CDN error state changed; discard copy");
    if(u32(cdn+0x34)!=contextRef || u32(cdn+0x38)!=contextControl ||
       u32(contextRef)!=context || u32(contextControl)!=base+0x213c8d8L ||
       (int)u32(contextControl+4)<0 || u32(contextControl+0x10)!=allocation ||
       (int)u32(allocation+4)<0)
      throw new IllegalStateException("CDN header context owner changed; discard copy");
    java.nio.file.Path parent=java.nio.file.Path.of("recovered-assets","cdn-cache-20261010","jdwp-current");
    java.nio.file.Files.createDirectories(parent);
    java.nio.file.Path out=java.nio.file.Files.createTempDirectory(parent,"current-");
    java.nio.file.Files.write(out.resolve("CURRENT"),current);
    java.nio.file.Files.write(out.resolve(name),manifest);
    java.nio.file.Files.write(out.resolve("directory-names.txt"),cacheFileNames,StandardCharsets.UTF_8);
    if(errorState!=null)java.nio.file.Files.write(out.resolve("native-error-state.bin"),errorState);
    for(var selected:copies.entrySet())java.nio.file.Files.write(out.resolve(selected.getKey()),selected.getValue());
    System.out.printf("Clone CDN metadata copied read-only: CURRENT=%d manifest=%d host=%s%n",
      current.length,manifest.length,out.toAbsolutePath());
    System.out.printf("Additional selected CDN files=%d bytes=%d%n",copies.size(),copies.values().stream().mapToInt(b -> b.length).sum());
    System.out.println("Live CDN binding verified: default encrypted adapter, namespace CDN, mode3, copied clone path.");
    System.out.println("Current public CDN header="+currentHeader);
    System.out.println("CDN LevelDB sticky background/write error present="+(backgroundError!=0));
    System.out.println("CDN LevelDB error code="+errorCode+" category="+errorCategory);
    System.out.println("CDN directory file count="+cacheFileNames.size()+" (names retained privately)");
    System.out.println("No cache values printed; byte recheck is not a durable database snapshot guarantee.");
  }
  static List<String> cdnDirectoryNames(String path) throws Exception {
    ClassType fileType=(ClassType)uniqueType("java.io.File");
    ObjectReference directory=fileType.newInstance(thread,method(fileType,"<init>","(Ljava/lang/String;)V"),
      List.of(vm.mirrorOf(path)),ObjectReference.INVOKE_SINGLE_THREADED);
    ArrayReference names=(ArrayReference)directory.invokeMethod(thread,method(fileType,"list","()[Ljava/lang/String;"),
      List.of(),ObjectReference.INVOKE_SINGLE_THREADED);
    if(names==null || names.length()>128)throw new IllegalStateException("CDN directory enumeration outside bound");
    List<String> result=new ArrayList<>();
    for(Value name:names.getValues()) {
      String text=((StringReference)name).value();
      if(text.length()>96 || text.contains("/") || text.contains("\\"))
        throw new IllegalStateException("CDN directory filename outside bound");
      result.add(text);
    }
    Collections.sort(result);return result;
  }
  static byte[] readCdnFile(String path,int maximum) throws Exception {
    ObjectReference file=open(path);
    try {
      long length=((LongValue)file.invokeMethod(thread,method(rafType,"length","()J"),
        List.of(),ObjectReference.INVOKE_SINGLE_THREADED)).value();
      if(length<0 || length>maximum)throw new IllegalStateException("CDN file size outside diagnostic bound");
      java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream((int)length);
      while(out.size()<length) {
        byte[] block=read(file,(int)Math.min(4096,length-out.size()));
        if(block.length==0)throw new IllegalStateException("truncated CDN file");
        out.write(block);
      }
      return out.toByteArray();
    } finally {close(file);}
  }
  static void inspectVillageUi(long base) throws Exception {
    Map<Long,String> types=uiTypes(base);
    long app=u32(base+0x21ef1e0L),manager=u32(app+8);
    if(u32(manager)!=base+0x21735a4L) throw new IllegalStateException("unexpected scene manager");
    long scene=u32(manager+0x34),control=u32(manager+0x38);
    if(u32(scene)!=base+0x216b1c4L || control==0 || (int)u32(control+4)<0)
      throw new IllegalStateException("current scene is not live Village");
    long view=u32(scene+0x98);
    if(u32(view)!=base+0x213a750L) throw new IllegalStateException("unknown Village view class");
    long root=u32(view+8);
    if(u32(root)!=base+0x213baccL) throw new IllegalStateException("unknown Village root class");
    Map<Long,Long> links=new LinkedHashMap<>();Set<Long> objects=new HashSet<>();StringBuilder result=new StringBuilder();
    walkFuelUi(base,root,"village",0,types,links,objects,result);
    for(var link:links.entrySet()) if(u32(link.getKey())!=link.getValue()) throw new IllegalStateException("Village graph changed");
    if(u32(manager+0x34)!=scene || u32(manager+0x38)!=control || (int)u32(control+4)<0 || u32(scene+0x98)!=view || u32(view+8)!=root)
      throw new IllegalStateException("Village scene changed; discard snapshot");
    System.out.printf("Village UI guarded nodes=%d%n",objects.size());System.out.print(result);
  }
  static void inspectFuelUi(long base) throws Exception {
    Map<Long,String> types=uiTypes(base);
    long holder=base+0x21e57f8L,modal=u32(holder),control=u32(holder+4);
    if(modal==0 || control==0 || u32(control)!=base+0x2186a38L || (int)u32(control+4)<0 || u32(control+0xc)!=modal)
      throw new IllegalStateException("unexpected or expired modal owner");
    long secondary=u32(modal+0x18),primary=u32(modal+0xc);
    long count=secondary>0?secondary:primary,back=u32(modal+(secondary>0?0x10:4));
    if(count<1 || count>32) throw new IllegalStateException("no bounded top modal");
    long top=u32(back+8);
    long topVptr=u32(top);
    if(topVptr!=base+0x2167d04L) throw new IllegalStateException("top modal is not Fuel popup: ELFvptr="+
      Long.toHexString(topVptr-base)+" class="+types.getOrDefault(topVptr,"UNKNOWN"));
    long view=u32(top+0x98);
    if(u32(view)!=base+0x213a750L) throw new IllegalStateException("unknown Fuel view class");
    long root=u32(view+8);
    if(u32(root)!=base+0x213baccL) throw new IllegalStateException("unknown Fuel root class");
    Map<Long,Long> links=new LinkedHashMap<>();
    Set<Long> objects=new HashSet<>();StringBuilder result=new StringBuilder();
    walkFuelUi(base,root,"root",0,types,links,objects,result);
    for(var link:links.entrySet()) if(u32(link.getKey())!=link.getValue())
      throw new IllegalStateException("UI child graph changed; discard snapshot");
    if(u32(holder)!=modal || u32(holder+4)!=control || (int)u32(control+4)<0 || u32(control+0xc)!=modal ||
       u32(modal+0x18)!=secondary || u32(modal+0xc)!=primary || u32(modal+(secondary>0?0x10:4))!=back ||
       u32(back+8)!=top || u32(top+0x98)!=view || u32(view+8)!=root)
      throw new IllegalStateException("Fuel modal changed; discard snapshot");
    System.out.printf("Fuel UI guarded nodes=%d top=%x root=%x%n",objects.size(),top,root);
    System.out.print(result);
  }
  static void walkFuelUi(long base,long object,String path,int depth,Map<Long,String> types,
      Map<Long,Long> links,Set<Long> objects,StringBuilder result) throws Exception {
    if(depth>16 || objects.size()>=256 || !objects.add(object)) throw new IllegalStateException("UI graph bound or object cycle");
    long vptr=u32(object);String type=types.get(vptr);
    if(type==null) throw new IllegalStateException("unknown/secondary UI vptr; inconclusive snapshot: "+Long.toHexString(vptr));
    String name=cppString(object+0x258,64);
    if(Set.of("PA_CELL0","PA_CELL1","PA_CELL2","PA_CELL3","PA_CELL_LIST","PA_IMG","BT_GET","RW_DAY",
        "BG_ACTIVE","BG_DISABLE","TX_GET","RW_STAMP","RW_IT_NUM","local_fuel_0",
        "PA_ICON_AREA","PA_ACTIVE","BT_ACTIVE","MN_NC","RE_LEFTUPPER","RE_MA_ICONR2").contains(name))
      result.append(String.format("UI path=%s name=%s class=%s object=%x hidden=%d%n",path,name,type,object,memory(object+0x271,1)[0]&255));
    if(vptr==base+0x2167e90L) {
      String template=cppString(object+0x824,64);long cached=u32(object+0x830),cachedCtrl=u32(object+0x834);
      links.put(object+0x830,cached);links.put(object+0x834,cachedCtrl);
      if(cached!=0 && (cachedCtrl==0 || (int)u32(cachedCtrl+4)<0 || !types.containsKey(u32(cached))))
        throw new IllegalStateException("unrecognized/expired Fuel template root");
      long cachedFirst=cached==0?0:u32(cached+0x4c);
      if(cached!=0) links.put(cached+0x4c,cachedFirst);
      result.append(String.format("FuelCell path=%s template=%s cachedRoot=%x cachedClass=%s cachedChildrenEmpty=%s firstChild=%x%n",path,
        template,cached,cached==0?"NULL":types.get(u32(cached)),cached==0?"NULL":Boolean.toString(cachedFirst==cached+0x48),u32(object+0x4c)));
    }
    long sentinel=object+0x48,first=u32(object+0x4c),node=first;
    links.put(object+0x4c,first);Set<Long> visited=new HashSet<>();int index=0;
    while(node!=sentinel) {
      if(index>=64 || !visited.add(node)) throw new IllegalStateException("UI sibling bound/cycle");
      long child=u32(node+8),childCtrl=u32(node+0xc),next=u32(node+4);
      if(childCtrl==0 || (int)u32(childCtrl+4)<0) throw new IllegalStateException("expired UI child");
      links.put(node+4,next);links.put(node+8,child);links.put(node+0xc,childCtrl);
      walkFuelUi(base,child,path+"."+index,depth+1,types,links,objects,result);
      node=next;index++;
    }
  }
  static void inspectItemReferences(long base) throws Exception {
    // Original typed singleton weak pair; plain CSRItemInfo, no object vptr.
    long holder=base+0x21d3ad4L,info=u32(holder),control=u32(holder+4);
    if(info==0 || control==0 || u32(control)!=base+0x2151cdcL || (int)u32(control+4)<0 || u32(control+0xc)!=info)
      throw new IllegalStateException("Item reference singleton owner unavailable/unproved");
    byte[] object=memory(info,0x30);long minimum=u32(info),root=u32(info+4),count=u32(info+8),owners=u32(control+4);
    if(count>4096 || (count==0 && (root!=0 || minimum!=info+4)) || (count!=0 && root==0))
      throw new IllegalStateException("Item reference tree header invalid");
    Map<Long,byte[]> nodes=new LinkedHashMap<>();Map<Long,String> keys=new LinkedHashMap<>(),thumbs=new LinkedHashMap<>();
    StringBuilder output=new StringBuilder(String.format("Item references owner=default_delete_verified count=%d nativeGettersCalled=false%n",count));
    for(String wanted:List.of("VIP1","RP1","DUMMY")) {
      long node=root,parent=info+4;Set<Long> path=new HashSet<>();boolean found=false;
      while(node!=0) {
        if((node&3)!=0 || path.size()>=32 || path.size()>=count || !path.add(node))
          throw new IllegalStateException("Item reference search depth/cycle invalid");
        byte[] bytes=memory(node,0x6c);byte[] prior=nodes.putIfAbsent(node,bytes);
        if(prior!=null && !Arrays.equals(prior,bytes)) throw new IllegalStateException("Item reference node changed");
        if(u32(node+8)!=parent) throw new IllegalStateException("Item reference parent link mismatch");
        String key=cppString(node+0x10,64);String oldKey=keys.putIfAbsent(node,key);
        if(key.chars().anyMatch(character->character>127))
          throw new IllegalStateException("Item reference non-ASCII key unsupported; no missing-key inference");
        if(oldKey!=null && !oldKey.equals(key)) throw new IllegalStateException("Item reference key changed");
        int compare=Arrays.compareUnsigned(wanted.getBytes(StandardCharsets.UTF_8),key.getBytes(StandardCharsets.UTF_8));
        if(compare==0) {
          String thumbnail=cppString(node+0x1c+0x38,64);thumbs.put(node,thumbnail);
          output.append(String.format("Item reference key=%s thumbnail=%s info=inline_verified displayRendering=unproved%n",wanted,thumbnail));
          found=true;break;
        }
        parent=node;node=u32(node+(compare<0?0:4));
      }
      if(!found) output.append("Item reference key="+wanted+" MISSING fallbackNotInvoked=true\n");
    }
    for(var row:nodes.entrySet()) if(!Arrays.equals(row.getValue(),memory(row.getKey(),0x6c)) || !keys.get(row.getKey()).equals(cppString(row.getKey()+0x10,64)))
      throw new IllegalStateException("Item reference node/key snapshot changed");
    for(var row:thumbs.entrySet()) if(!row.getValue().equals(cppString(row.getKey()+0x54,64)))
      throw new IllegalStateException("Item reference thumbnail changed");
    if(u32(holder)!=info || u32(holder+4)!=control || u32(control)!=base+0x2151cdcL || u32(control+4)!=owners || u32(control+0xc)!=info ||
       !Arrays.equals(object,memory(info,0x30)) || u32(info)!=minimum || u32(info+4)!=root || u32(info+8)!=count)
      throw new IllegalStateException("Item reference owner/tree changed");
    System.out.print(output);
  }
  static float finiteFloat(long address) throws Exception {
    float value=Float.intBitsToFloat((int)u32(address));
    if(!Float.isFinite(value)) throw new IllegalStateException("Nonfinite skill reference float");
    return value;
  }
  static void retainSkillBytes(Map<Long,byte[]> snapshots,long address,int length) throws Exception {
    byte[] bytes=memory(address,length),prior=snapshots.putIfAbsent(address,bytes);
    if(prior!=null && !Arrays.equals(prior,bytes)) throw new IllegalStateException("Skill reference capture changed");
  }
  static void verifySkillTreeMinimum(Map<Long,byte[]> snapshots,long root,long minimum,long count,int nodeSize) throws Exception {
    Set<Long> path=new HashSet<>();long node=root;
    while(node!=0) {
      if((node&3)!=0 || path.size()>=32 || path.size()>=count || !path.add(node)) throw new IllegalStateException("Tree minimum bound/cycle");
      retainSkillBytes(snapshots,node,nodeSize);
      long left=u32(node);
      if(left==0) {if(node!=minimum) throw new IllegalStateException("Tree minimum mismatch");return;}
      if(u32(left+8)!=node) throw new IllegalStateException("Tree minimum parent mismatch");
      node=left;
    }
    throw new IllegalStateException("Tree minimum unavailable");
  }
  static void inspectSkillReferences(long base) throws Exception {
    // Original CSRCardInfo emplace +c/plain b8, normal skill tree and result lists.
    Map<Long,byte[]> snapshots=new LinkedHashMap<>();Map<Long,String> strings=new LinkedHashMap<>();
    long holder=base+0x21cf2d0L,container=u32(holder),owner=u32(holder+4);
    if(container==0 || owner==0 || (container&3)!=0 || (owner&3)!=0 || u32(owner)!=base+0x2141730L || (int)u32(owner+4)<0 || u32(owner+0xc)!=container)
      throw new IllegalStateException("Skill reference singleton owner unavailable");
    retainSkillBytes(snapshots,holder,8);retainSkillBytes(snapshots,owner,0x10);retainSkillBytes(snapshots,container,0xc);
    long root=u32(container+4),count=u32(container+8);
    if(count==0 || count>4096 || root==0) throw new IllegalStateException("Card reference header invalid");
    verifySkillTreeMinimum(snapshots,root,u32(container),count,0x24);
    StringBuilder out=new StringBuilder("Ordinary skill reference snapshot nativeGettersCalled=false activation=unproved\n");
    for(String wanted:List.of("001","003","004")) {
      long node=root,parent=container+4;Set<Long> path=new HashSet<>();boolean found=false;
      while(node!=0) {
        if((node&3)!=0 || path.size()>=32 || path.size()>=count || !path.add(node)) throw new IllegalStateException("Card lookup bound/cycle");
        retainSkillBytes(snapshots,node,0x24);
        if(u32(node+8)!=parent) throw new IllegalStateException("Card parent mismatch");
        String key=cppString(node+0x10,64);strings.put(node+0x10,key);
        if(key.chars().anyMatch(c->c>127)) throw new IllegalStateException("Non-ASCII reference key unsupported");
        int compare=wanted.compareTo(key);
        if(compare!=0){parent=node;node=u32(node+(compare<0?0:4));continue;}
        long card=u32(node+0x1c),control=u32(node+0x20);
        if(card==0 || control==0 || (card&3)!=0 || (control&3)!=0 || card!=control+0xc || u32(control)!=base+0x214166cL || (int)u32(control+4)<0)
          throw new IllegalStateException("CardInfo emplace owner mismatch");
        retainSkillBytes(snapshots,control,0xc);retainSkillBytes(snapshots,card,0xb8);
        String identity=cppString(card,64);strings.put(card,identity);
        if(!identity.equals(wanted)) throw new IllegalStateException("Card identity mismatch");
        long skillRoot=u32(card+0xb0),skillCount=u32(card+0xb4);
        if(skillCount!=5 || skillRoot==0) throw new IllegalStateException("Expected five normal reference slots");
        verifySkillTreeMinimum(snapshots,skillRoot,u32(card+0xac),skillCount,0x74);
        for(int type=1;type<=5;type++) {
          long skill=skillRoot,skillParent=card+0xb0;Set<Long> skillPath=new HashSet<>();boolean slotFound=false;
          while(skill!=0) {
            if((skill&3)!=0 || skillPath.size()>=skillCount || !skillPath.add(skill)) throw new IllegalStateException("Skill lookup bound/cycle");
            retainSkillBytes(snapshots,skill,0x74);
            if(u32(skill+8)!=skillParent) throw new IllegalStateException("Skill parent mismatch");
            long keyType=u32(skill+0x10);
            if(keyType!=type){skillParent=skill;skill=u32(skill+(type<keyType?0:4));continue;}
            long info=skill+0x14;
            if(u32(info+0x28)!=type) throw new IllegalStateException("Skill key/type mismatch");
            long sentinel=info+0x2c,last=u32(sentinel),effectNode=u32(sentinel+4),effectCount=u32(sentinel+8);
            if(effectCount>16) throw new IllegalStateException("Effect count exceeds scope");
            out.append(String.format("card=%s slot=%d rank=%d cost=%d critical=%d cooldownSeconds=%f effects=%d%n",wanted,type,u32(info),u32(info+0x48),u32(info+0x4c),finiteFloat(info+0x50),effectCount));
            long previous=sentinel;Set<Long> effects=new HashSet<>();
            for(int index=0;index<effectCount;index++) {
              if(effectNode==sentinel || (effectNode&3)!=0 || !effects.add(effectNode)) throw new IllegalStateException("Effect list truncated/cyclic");
              retainSkillBytes(snapshots,effectNode,0xc0);
              if(u32(effectNode)!=previous) throw new IllegalStateException("Effect previous link mismatch");
              long effect=effectNode+8;
              out.append(String.format(" effect=%d serial=%d target=%d stat=%d referStat=%d referType=%d kind=%d delay=%f base=%f up=%f duration=%f durationUp=%f interval=%f rawInteger30=%d nestedA=%d nestedB=%d%n",index,u32(effect),u32(effect+4),u32(effect+8),u32(effect+0xc),u32(effect+0x10),u32(effect+0x14),finiteFloat(effect+0x18),finiteFloat(effect+0x1c),finiteFloat(effect+0x20),finiteFloat(effect+0x24),finiteFloat(effect+0x28),finiteFloat(effect+0x2c),(int)u32(effect+0x30),u32(effect+0xa8),u32(effect+0xb4)));
              previous=effectNode;effectNode=u32(effectNode+4);
            }
            if(effectNode!=sentinel || previous!=last) throw new IllegalStateException("Effect list tail/count mismatch");
            slotFound=true;break;
          }
          if(!slotFound) throw new IllegalStateException("Mandatory skill slot absent");
        }
        found=true;break;
      }
      if(!found) throw new IllegalStateException("Selected card absent");
    }
    for(var row:snapshots.entrySet()) if(!Arrays.equals(row.getValue(),memory(row.getKey(),row.getValue().length))) throw new IllegalStateException("Skill reference bytes changed");
    for(var row:strings.entrySet()) if(!row.getValue().equals(cppString(row.getKey(),64))) throw new IllegalStateException("Skill reference string changed");
    System.out.print(out);
  }
  static void inspectCards(long base) throws Exception {
    long holder=base+0x21cf2d0L,container=u32(holder),control=u32(holder+4);
    if(container==0 || control==0) {System.out.println("card singleton unavailable");return;}
    long controlVtable=u32(control);int owners=(int)u32(control+4);
    System.out.printf("card singleton=%x control=%x owners=%d controlVtable=%x%n",container,control,owners,controlVtable);
    if(controlVtable!=base+0x2141730L || owners<0 || u32(control+0xc)!=container)
      throw new IllegalStateException("card singleton expired or control type mismatch");
    long root=u32(container+4),count=u32(container+8);
    StringBuilder result=new StringBuilder(String.format("card container=%x count=%d root=%x%n",container,count,root));
    Set<String> observedKeys=new TreeSet<>();
    for(String wanted:List.of("001","002","003","004")) {
      long node=root;Set<Long> visited=new HashSet<>();boolean found=false;
      for(int depth=0;node!=0 && depth<32;depth++) {
        if(!visited.add(node)) throw new IllegalStateException("card-map cycle");
        String key=cppString(node+0x10);observedKeys.add(key);int compare=wanted.compareTo(key);
        if(compare==0) {
          long info=u32(node+0x1c);
          result.append(String.format("card key=%s info=%x",key,info));
          if(info!=0) result.append(String.format(" infoId=%s prefix=%s training=%d",cppString(info),cppString(info+0xc),memory(info+0x3c,1)[0]&255));
          result.append('\n');found=true;break;
        }
        node=u32(node+(compare<0?0:4));
      }
      if(node!=0 && !found) throw new IllegalStateException("card-map search depth exceeds32");
      if(!found) result.append("card key="+wanted+" MISSING\n");
    }
    result.append("bounded search keys="+observedKeys+"\n");
    // Weak owner and tree can change while native callbacks run. Reject a
    // changed snapshot rather than combine two registrations into one claim.
    if(u32(holder)!=container || u32(holder+4)!=control || (int)u32(control+4)<0 ||
       u32(control+0xc)!=container || u32(container+4)!=root || u32(container+8)!=count)
      throw new IllegalStateException("card registration changed; discard snapshot");
    System.out.print(result);
  }
  static void inspect() throws Exception {
    ClassType cls=(ClassType)vm.classesByName("java.lang.Class").get(0);
    cls.invokeMethod(thread,method(cls,"forName","(Ljava/lang/String;)Ljava/lang/Class;"),
      List.of(vm.mirrorOf("java.io.RandomAccessFile")),ClassType.INVOKE_SINGLE_THREADED);
    rafType=(ClassType)vm.classesByName("java.io.RandomAccessFile").get(0);
    bytesType=(ArrayType)vm.classesByName("byte[]").stream().findFirst().orElseGet(() -> vm.classesByName("[B").get(0));
    ObjectReference maps=open("/proc/self/maps");
    StringBuilder text=new StringBuilder();
    try {
      for(int i=0;i<256;i++) { byte[] block=read(maps,4096); if(block.length==0) break;
        text.append(new String(block,StandardCharsets.US_ASCII)); }
    } finally { close(maps); }
    long base=0;
    for(String line:text.toString().split("\n")) {
      String[] columns=line.trim().split("\\s+",6);
      if(columns.length<5) continue;
      String[] range=columns[0].split("-");
      long start=Long.parseUnsignedLong(range[0],16),end=Long.parseUnsignedLong(range[1],16);
      regions.add(new Region(start,end,columns[1].startsWith("r")));
      if(columns.length==6 && columns[5].endsWith("/libnative_core.so") && Long.parseUnsignedLong(columns[2],16)==0) base=start;
    }
    if(base==0) throw new IllegalStateException("native core offset0 mapping missing");
    mem=open("/proc/self/mem");
    try {
      if(cdnCurrentOnly) {inspectCdnCurrent(base);return;}
      if(arenaConfirmOnly) {inspectArenaConfirm(base);return;}
      if(cardsOnly) {inspectCards(base);return;}
      if(itemReferencesOnly) {inspectItemReferences(base);return;}
      if(skillReferencesOnly) {inspectSkillReferences(base);return;}
      if(supplyOnly) {inspectSupply(base);return;}
      if(combatTuningOnly) {inspectCombatTuning(base);return;}
      if(fuelUiOnly) {inspectFuelUi(base);return;}
      if(villageUiOnly) {inspectVillageUi(base);return;}
      if(gymSourcesOnly) {inspectGymSources(base);return;}
      if(guideStateOnly) {inspectGuideState(base);return;}
      if(resultUiOnly) {inspectResultUi(base);return;}
      if(campaignMarkersOnly) {inspectCampaignMarkers(base);return;}
      if(fishingHookOnly) {inspectFishingHook(base);return;}
      if(rendererLayoutOnly || touchLayoutOnly) {inspectRendererLayout(base);if(!episodeTouchOnly)return;}
      if(episodeControlsOnly) {inspectEpisodeControls(base);return;}
      if(episodeSceneOnly) {inspectEpisodeScene(base);return;}
      long app=u32(base+0x21ef1e0L),manager=u32(app+8);
      long managerVtable=u32(manager);
      System.out.printf("native base=%x app=%x manager=%x managerVtable=%x%n",base,app,manager,managerVtable);
      if(managerVtable!=base+0x21735a4L) throw new IllegalStateException("unexpected manager vtable");
      System.out.printf("manager loadingFlag=%d faderEnd=%d%n",memory(manager+0x32,1)[0]&255,memory(manager+0x673,1)[0]&255);
      long scene=u32(manager+0x34),sceneVtable=u32(scene);
      System.out.printf("native base=%x scene=%x vtable=%x%n",base,scene,sceneVtable);
      if(sceneVtable!=base+0x216f90cL) {System.out.println("not CSRSceneGame; no gameplay reads");return;}
      long game=u32(scene+0x658),mode=u32(scene+0x660),gameVtable=u32(game);
      System.out.printf("game candidate=%x mode=%d vtable=%x%n",game,mode,gameVtable);
      if(!Set.of(base+0x2153f84L,base+0x2179248L,base+0x217ac04L).contains(gameVtable))
        throw new IllegalStateException("unrecognized game vtable; no field reads");
      System.out.printf("game=%x mode=%d vtable=%x pause=%x state=%x caught=%x%n",game,mode,gameVtable,
        u32(game+0x140),memory(game+0x13c,1)[0]&255,u32(game+0x198));
      inspectGroups(base,game);
      System.out.printf("input actor count=%d%n",u32(game+0x184));
      long sentinel=game+0x17c,node=u32(game+0x180);
      Set<Long> visited=new HashSet<>();
      for(int i=0;node!=sentinel && i<32;i++) {
        if(!visited.add(node)) throw new IllegalStateException("input list cycle");
        long actor=u32(node+8),actorVtable=u32(actor);
        if(!Set.of(base+0x214a3fcL,base+0x214a638L,base+0x21494ccL).contains(actorVtable))
          throw new IllegalStateException("unknown actor vtable");
        long defaults=u32(actor+0x8b4),buff=u32(actor+0x8bc);
        System.out.printf("input actor=%x vt=%x group=%s binding=%x clock=%f lastAtk=%f interval=%f multiplier=%f stun=%d hold=%d chargeAtk=%f chargeKill=%f%n",
          actor,actorVtable,cppString(actor+0x898),u32(actor+0xa6c),f32(actor+0x228),f32(actor+0xa68),f32(defaults+0x3c),f32(buff+0x3c),u32(buff+0x94),u32(buff+0x98),f32(defaults+0x70),f32(defaults+0x78));
        node=u32(node+4);
      }
    } finally {close(mem);}
  }
  public static void main(String[] args) throws Exception {
    episodeControlsOnly=NativeBattleControls.parseMode(args);
    episodeFeverOnly=parseEpisodeFeverMode(args);
    episodeHealSource=parseHealSourceSelection(args);
    cardsOnly=args.length>1 && args[1].equals("--cards");
    arenaConfirmOnly=args.length>1 && args[1].equals("--arena-confirm");
    itemReferencesOnly=args.length>1 && args[1].equals("--item-references");
    skillReferencesOnly=args.length>1 && args[1].equals("--skill-references");
    supplyOnly=args.length>1 && args[1].equals("--supply");
    combatTuningOnly=args.length>1 && args[1].equals("--combat-tuning");
    fuelUiOnly=args.length>1 && args[1].equals("--fuel-ui");
    villageUiOnly=args.length>1 && args[1].equals("--village-ui");
    gymSourcesOnly=args.length>1 && args[1].equals("--gym-sources");
    guideStateOnly=args.length>1 && args[1].equals("--guide-state");
    resultUiOnly=args.length>1 && args[1].equals("--result-ui");
    campaignMarkersOnly=args.length>1 && args[1].equals("--campaign-markers");
    cdnCurrentOnly=args.length>1 && args[1].equals("--cdn-current");
    cdnCopySpec=cdnCurrentOnly && args.length>3?args[3]:null;
    if(cdnCurrentOnly && args.length>4)throw new IllegalArgumentException("Unexpected CDN metadata arguments");
    fishingHookOnly=args.length>1 && args[1].equals("--fishing-hook");
    episodeTouchOnly=args.length>1 && args[1].equals("--episode-touch");
    episodeBadgeOnly=parseEpisodeBadgeMode(args);
    for(int arg=2;arg<args.length;arg++) if(args[arg].startsWith("--source-serial=") && !episodeTouchOnly)
      throw new IllegalArgumentException("Source selection requires --episode-touch");
    if(episodeTouchOnly) {
      for(int arg=2;arg<args.length;arg++) {
        if(args[arg].equals("--skip-events=2") && episodeTouchSkipEvents==0) episodeTouchSkipEvents=2;
        else if(args[arg].matches("--source-serial=[1-9][0-9]{0,9}") && episodeTouchSourceSerial==0) {
          episodeTouchSourceSerial=Long.parseLong(args[arg].substring("--source-serial=".length()));
          if(episodeTouchSourceSerial>0xffffffffL) throw new IllegalArgumentException("Source serial exceeds low-word scope");
        } else throw new IllegalArgumentException("Episode touch accepts unique --skip-events=2 and --source-serial=<positive low word>");
      }
    }
    episodeSkillsOnly=episodeTouchOnly || (args.length>1 && args[1].equals("--episode-skills"));
    episodeExchangeOnly=args.length>1 && args[1].equals("--episode-exchange");
    rendererLayoutOnly=args.length>1 && args[1].equals("--renderer-layout");
    touchLayoutOnly=episodeTouchOnly || (args.length>1 && args[1].equals("--touch-layout"));
    episodeMaterialsOnly=episodeSkillsOnly || episodeExchangeOnly || (args.length>1 && args[1].equals("--episode-materials"));
    episodeSceneOnly=args.length>1 && (args[1].equals("--episode-scene") || episodeMaterialsOnly || episodeBadgeOnly || episodeFeverOnly);
    AttachingConnector connector=Bootstrap.virtualMachineManager().attachingConnectors().stream()
      .filter(c -> c.name().equals("com.sun.jdi.SocketAttach")).findFirst().orElseThrow();
    var config=connector.defaultArguments();config.get("hostname").setValue("127.0.0.1");
    config.get("port").setValue(args.length>0?args[0]:"8701");vm=connector.attach(config);
    try {
      if(vm.classesByName("com.vshower.instrumented.InstrumentedActivity").isEmpty())
        throw new IllegalStateException("instrumented target identity not found");
      boolean frameSnapshot=args.length>2 && args[2].equals("--frame");
      if(arenaConfirmOnly && (!frameSnapshot || args.length!=3)) throw new IllegalArgumentException("Arena confirm requires only --frame");
      if(itemReferencesOnly&&!frameSnapshot) throw new IllegalArgumentException("Item references require --frame");
      if(skillReferencesOnly&&!frameSnapshot) throw new IllegalArgumentException("Skill references require --frame");
      if(episodeExchangeOnly&&!frameSnapshot) throw new IllegalArgumentException("Exchange diagnostic requires --frame");
      if(campaignMarkersOnly&&!frameSnapshot) throw new IllegalArgumentException("Campaign markers require --frame");
      if(cdnCurrentOnly&&!frameSnapshot) throw new IllegalArgumentException("CDN file metadata requires --frame");
      if(resultUiOnly&&!frameSnapshot) throw new IllegalArgumentException("Result UI diagnostic requires --frame");
      if(rendererLayoutOnly&&!frameSnapshot) throw new IllegalArgumentException("Renderer layout requires --frame");
      Method snapshotMethod;
      if(touchLayoutOnly) {
        if(frameSnapshot) throw new IllegalArgumentException("Touch layout requires one explicit safe-menu touch, not --frame");
        snapshotMethod=uniqueType("com.vshower.rann.RMFrameworkActivity").methodsByName("onTouchEvent","(Landroid/view/MotionEvent;)Z").get(0);
      } else if(frameSnapshot) {
        // Original com.vshower.rann.b implements GLSurfaceView.Renderer;
        // JADX renamed it C3159b. Select the unique loaded native-shell renderer.
        List<Method> renderMethods=new ArrayList<>();
        for(ReferenceType type:vm.allClasses()) if(type.name().startsWith("com.vshower.rann."))
          for(Method candidate:type.methodsByName("onDrawFrame","(Ljavax/microedition/khronos/opengles/GL10;)V"))
            if(!candidate.isAbstract() && !candidate.isNative()) renderMethods.add(candidate);
        if(renderMethods.size()!=1) throw new IllegalStateException("unique original render callback unavailable; no input fallback");
        snapshotMethod=renderMethods.get(0);
        System.out.println("Read-only render callback: "+snapshotMethod.declaringType().name()+".onDrawFrame");
      } else {
        ReferenceType activity=vm.classesByName("android.app.Activity").get(0);
        snapshotMethod=activity.methodsByName("dispatchTouchEvent").get(0);
      }
      var breakpoint=vm.eventRequestManager().createBreakpointRequest(snapshotMethod.location());
      // Report this breakpoint only once through its count filter. disable() while
      // handling a SUSPEND_ALL event stalled JDWP EventRequest.Clear on the
      // live BlueStacks client (observer44348); do not clear before reading.
      // Optional two-event skip is for an explicit normal Resume tap (DOWN/UP)
      // while already paused. It is not an action classifier: the reported
      // event still must pass actual single-DOWN identity/conversion checks.
      breakpoint.addCountFilter(1+episodeTouchSkipEvents);
      breakpoint.setSuspendPolicy(EventRequest.SUSPEND_ALL);breakpoint.enable();
      System.out.println(frameSnapshot ? "Waiting up to30s for instrumented render frame; read-only snapshot, no input." : "Waiting up to30s for instrumented activity tap; read-only snapshot.");
      long deadline=System.currentTimeMillis()+30000;
      while(System.currentTimeMillis()<deadline) {
        EventSet events=vm.eventQueue().remove(1000);if(events==null)continue;
        try {for(Event event:events)if(event instanceof BreakpointEvent hit){
          thread=hit.thread();long snapshotStarted=System.nanoTime();
          try {inspect();} finally {
            System.out.printf(Locale.ROOT,"Observer transport memoryReadCalls=%d requestedBytes=%d memoryReadSeconds=%.6f snapshotSeconds=%.6f selectedSourceSerial=%d nativeInputLatency=unproved%n",
              memoryReadCalls,memoryRequestedBytes,memoryReadNanos/1e9,(System.nanoTime()-snapshotStarted)/1e9,episodeTouchSourceSerial);
          }
          return;
        }}
        finally {events.resume();}
      }
      throw new IllegalStateException(frameSnapshot ? "no render breakpoint observed" : "no touch breakpoint observed");
    } finally {
      for(ArrayReference buffer:readBuffers.values())try{buffer.enableCollection();}catch(RuntimeException ignored){}
      readBuffers.clear();vm.dispose();
    }
  }
}
