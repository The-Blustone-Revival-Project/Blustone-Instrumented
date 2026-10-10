import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
public final class TestNativeCampaignMarkers {
  static final class Heap {
    byte[] data=new byte[65536];int next=256;long forbidden;
    int alloc(int n){int p=next;next=(next+n+7)&~7;return p;}
    void u32(int p,long n){ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN).putInt(p,(int)n);}
    void string(int p,String text){byte[] b=text.getBytes(StandardCharsets.US_ASCII);
      if(b.length<=10){data[p]=(byte)(b.length<<1);System.arraycopy(b,0,data,p+1,b.length);}
      else{int a=alloc(b.length+1);u32(p,(b.length+16)&~15|1);u32(p+4,b.length);u32(p+8,a);System.arraycopy(b,0,data,a,b.length);}}
    int number(long n){int p=alloc(16);data[p]=5;ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN).putLong(p+8,n);return p;}
    int text(String value){int p=alloc(16),s=alloc(12);data[p]=3;u32(p+8,s);string(s,value);return p;}
    int object(Map<String,Integer> fields){int p=alloc(16),map=alloc(12);data[p]=1;u32(p+8,map);
      List<String> keys=new ArrayList<>(fields.keySet());Collections.sort(keys);int[] nodes=new int[keys.size()];for(int i=0;i<nodes.length;i++)nodes[i]=alloc(48);
      for(int i=0;i<nodes.length;i++){data[nodes[i]+12]=1;string(nodes[i]+16,keys.get(i));System.arraycopy(data,fields.get(keys.get(i)),data,nodes[i]+32,16);}
      int root=link(nodes,0,nodes.length,map+4);u32(map, nodes.length==0?map+4:nodes[0]);u32(map+4,root);u32(map+8,nodes.length);return p;}
    int link(int[] n,int start,int end,int parent){if(start==end)return 0;int mid=(start+end)/2,p=n[mid];u32(p+8,parent);u32(p,link(n,start,mid,p));u32(p+4,link(n,mid+1,end,p));return p;}
    byte[] read(long p,int n){if(forbidden!=0 && p<=forbidden && p+n>forbidden)throw new AssertionError("unallowlisted value dereferenced");return Arrays.copyOfRange(data,(int)p,(int)p+n);}
    int u32(int p){return ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN).getInt(p);}
  }
  static void check(boolean value,String msg){if(!value)throw new AssertionError(msg);}
  static void reject(Heap h,int root) throws Exception {try{new NativeCampaignMarkers(h::read).project(root);throw new AssertionError("malformed tree accepted");}catch(IllegalStateException expected){}}
  public static void main(String[] args) throws Exception {
    Heap h=new Heap();int emptyObject=h.object(Map.of());check(new NativeCampaignMarkers(h::read).project(emptyObject).toString().contains("absent"),"empty object missing");int nul=h.alloc(16);Map<String,Object> empty=new NativeCampaignMarkers(h::read).project(nul);check(empty.toString().contains("absent"),"null must not allocate or invent markers");
    int secret=h.text("SECRET_BAIT");h.forbidden=h.u32(secret+8);
    int value=h.object(Map.of("autoplay",h.number(1),"stage",h.text("n_05_02"),"unknown_secret",secret));
    int root=h.object(Map.of("MissionAutoPlay",value,"OtherPrivate",secret,"MissionAutoPlayConfirm",h.object(Map.of("autoplay",h.number(0)))));
    Map<String,Object> result=new NativeCampaignMarkers(h::read).project(root);
    check(result.toString().contains("stage=n_05_02"),"canonical stage missing");check(result.toString().contains("autoplay=1"),"numeric marker missing");check(!result.toString().contains("SECRET"),"secret serialized");
    Heap unsupported=new Heap();int ur=unsupported.object(Map.of("MissionAutoPlay",unsupported.object(Map.of("autoplay",unsupported.text("SECRET_BAIT"),"stage",unsupported.text("PRIVATE_BAIT")))));
    String projected=new NativeCampaignMarkers(unsupported::read).project(ur).toString();check(!projected.contains("BAIT"),"invalid string leaked");check(projected.contains("unsupported"),"unsupported value hidden as valid");
    for(int stage=0;stage<=1;stage++){
      Heap numeric=new Heap();int nr=numeric.object(Map.of("MissionAutoPlay",numeric.object(Map.of("stage",numeric.number(stage)))));
      String output=new NativeCampaignMarkers(numeric::read).project(nr).toString();
      check(output.contains(stage==0?"stage=0":"stage=unsupported_number"),"numeric stage sentinel restriction");
    }
    for(int kind=0;kind<5;kind++){
      Heap broken=new Heap();int br=broken.object(Map.of("MissionAutoPlay",broken.object(Map.of("autoplay",broken.number(1)))));int map=broken.u32(br+8),node=broken.u32(map+4);
      if(kind==0)broken.u32(map+8,129);if(kind==1)broken.u32(node,node);if(kind==2)broken.u32(node+8,777);if(kind==3)broken.u32(map,999);
      if(kind==4){int inner=broken.u32(node+40),innerNode=broken.u32(inner+4);broken.data[innerNode+16+1+8]=1;}
      reject(broken,br);
    }
    Heap race=new Heap();int rr=race.object(Map.of("MissionAutoPlay",race.object(Map.of("autoplay",race.number(1)))));Map<String,Integer> counts=new HashMap<>();
    try{new NativeCampaignMarkers((p,n)->{String key=p+":"+n;int count=counts.merge(key,1,Integer::sum);byte[] b=race.read(p,n);if(p==rr && count>1)b[0]=0;return b;}).project(rr);throw new AssertionError("changed snapshot accepted");}catch(IllegalStateException expected){}
    Heap cdn=new Heap();int secretCdn=cdn.text("SECRET_ACCOUNT_VALUE");
    cdn.forbidden=ByteBuffer.wrap(cdn.data).order(ByteOrder.LITTLE_ENDIAN).getInt(secretCdn+8);
    int items=cdn.object(Map.of());
    int header=cdn.object(Map.of("stamp",cdn.number(1634683),"cnt",cdn.number(139),
      "size",cdn.number(212934524),"items",items,"account",secretCdn));
    Map<String,Object> ch=new NativeCampaignMarkers(cdn::read).projectCdnHeader(header);
    check(ch.get("stamp").equals(1634683L) && ch.get("item_count").equals(0L),"CDN object projection failed");
    check(!ch.toString().contains("SECRET") && !ch.containsKey("account"),"CDN private field exposed");
    Heap array=new Heap();int aj=array.alloc(16),vec=array.alloc(12),data=array.alloc(32);
    array.data[aj]=2;array.u32(aj+8,vec);array.u32(vec,data);array.u32(vec+4,data+32);array.u32(vec+8,data+32);
    int ah=array.object(Map.of("stamp",array.number(1),"cnt",array.number(2),"size",array.number(3),"items",aj));
    check(new NativeCampaignMarkers(array::read).projectCdnHeader(ah).get("item_count").equals(2L),"CDN array count failed");
    for(int fault=0;fault<4;fault++) {
      Heap bad=new Heap();int bj=bad.object(Map.of());
      if(fault==1)bad.u32(ByteBuffer.wrap(bad.data).order(ByteOrder.LITTLE_ENDIAN).getInt(bj+8)+8,257);
      int bh=bad.object(Map.of("stamp",fault==0?bad.text("private"):bad.number(1),
        "cnt",bad.number(2),"size",bad.number(fault==2?-1:3),"items",bj));
      final int currentFault=fault;Map<String,Integer> samples=new HashMap<>();
      try {
        new NativeCampaignMarkers((p,n)->{byte[] b=bad.read(p,n);int count=samples.merge(p+":"+n,1,Integer::sum);
          if(currentFault==3 && p==bh && count>1)b[0]=0;return b;}).projectCdnHeader(bh);
        throw new AssertionError("invalid CDN header accepted");
      } catch(IllegalStateException expected) {}
    }
    System.out.println("Marker and public CDN observers: privacy, object/array counts, invalid kinds/counts/numbers, corrupt trees and snapshot change passed.");
  }
}
