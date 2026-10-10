import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Original ARM32 JSON tree observer: only explicit public/marker projections. */
public final class NativeCampaignMarkers {
  @FunctionalInterface public interface Reader { byte[] read(long address,int size) throws Exception; }
  private record Read(long address,byte[] bytes) {}
  private final Reader reader;
  private final Map<String,byte[]> cache=new LinkedHashMap<>();
  private final List<Read> reads=new ArrayList<>();
  private final Set<Long> validatedObjects=new HashSet<>();
  public NativeCampaignMarkers(Reader reader){this.reader=reader;}
  private byte[] bytes(long address,int size) throws Exception {
    if(address<=0 || size<1 || size>4096) throw new IllegalStateException("bounded marker read rejected");
    String key=address+":"+size;
    if(cache.containsKey(key))return cache.get(key);
    for(Read r:reads)if(address>=r.address && address+size<=r.address+r.bytes.length)
      return Arrays.copyOfRange(r.bytes,(int)(address-r.address),(int)(address-r.address)+size);
    if(reads.size()>=512)throw new IllegalStateException("bounded marker read rejected");
    byte[] value=reader.read(address,size).clone();
    if(value.length!=size)throw new IllegalStateException("truncated marker read");
    cache.put(key,value);reads.add(new Read(address,value));return value;
  }
  private static long u32(byte[] b,int offset){return Integer.toUnsignedLong(ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN).getInt(offset));}
  private byte[] string(long address,int limit) throws Exception {
    byte[] h=bytes(address,12);int first=h[0]&255;int length;byte[] text;
    if((first&1)==0){length=first>>>1;if(length>10 || h[1+length]!=0)throw new IllegalStateException("invalid short marker key");text=Arrays.copyOfRange(h,1,1+length);}
    else{long n=u32(h,4),cap=u32(h,0)&~1L,p=u32(h,8);
      if(n>limit || cap<n+1 || cap>4096 || p==0)throw new IllegalStateException("unbounded marker string");
      length=(int)n;byte[] raw=bytes(p,length+1);if(raw[length]!=0)throw new IllegalStateException("unterminated marker string");text=Arrays.copyOf(raw,length);}
    if(length>limit)throw new IllegalStateException("unbounded marker key");return text;
  }
  private long find(long object,String wanted,int maximum) throws Exception {
    byte[] header=bytes(object,12);long minimum=u32(header,0),root=u32(header,4),count=u32(header,8),end=object+4;
    if(count>maximum)throw new IllegalStateException("marker map too large");
    if(count==0){if(root!=0 || minimum!=end)throw new IllegalStateException("invalid empty marker tree");return 0;}
    if(root==0 || minimum==0)throw new IllegalStateException("missing marker tree root");
    if(validatedObjects.add(object)) {
      Deque<long[]> stack=new ArrayDeque<>();stack.push(new long[]{root,end});Set<Long> nodes=new HashSet<>();
      while(!stack.isEmpty()) {
        long[] entry=stack.pop();long n=entry[0];
        if(!nodes.add(n) || nodes.size()>count)throw new IllegalStateException("cyclic/oversized marker tree");
        byte[] row=bytes(n,48);if(u32(row,8)!=entry[1] || (row[12]&255)>1)throw new IllegalStateException("invalid marker link/color");
        if(u32(row,0)!=0)stack.push(new long[]{u32(row,0),n});
        if(u32(row,4)!=0)stack.push(new long[]{u32(row,4),n});
      }
      if(nodes.size()!=count)throw new IllegalStateException("marker tree count mismatch");
      Deque<Long> path=new ArrayDeque<>();long cursor=root,first=0;byte[] previous=null;
      while(cursor!=0 || !path.isEmpty()) {
        while(cursor!=0){path.push(cursor);cursor=u32(bytes(cursor,48),0);}
        cursor=path.pop();if(first==0)first=cursor;
        byte[] key=string(cursor+16,96);
        if(previous!=null && Arrays.compareUnsigned(previous,key)>=0)throw new IllegalStateException("unordered marker tree");
        previous=key;cursor=u32(bytes(cursor,48),4);
      }
      if(first!=minimum)throw new IllegalStateException("marker minimum mismatch");
    }
    long node=root,parent=end;Set<Long> seen=new HashSet<>();byte[] name=wanted.getBytes(StandardCharsets.US_ASCII);
    for(int i=0;i<32 && node!=0;i++){
      if(!seen.add(node))throw new IllegalStateException("cyclic marker tree");
      byte[] n=bytes(node,48);long left=u32(n,0),right=u32(n,4);
      if(u32(n,8)!=parent || (n[12]&255)>1)throw new IllegalStateException("invalid marker parent/color");
      if(left!=0 && u32(bytes(left,48),8)!=node || right!=0 && u32(bytes(right,48),8)!=node)
        throw new IllegalStateException("broken marker child link");
      int comparison=Arrays.compareUnsigned(string(node+16,96),name);
      if(comparison==0)return node+32;
      parent=node;node=comparison>0?left:right;
    }
    if(node!=0)throw new IllegalStateException("marker lookup depth exceeded");return 0;
  }
  private Object scalar(long json,String member) throws Exception {
    byte[] b=bytes(json,16);int type=b[0]&255;
    if(type==0)return "null";
    if(type==4){int v=b[8]&255;return !member.equals("stage") && v<=1?v:"unsupported_boolean";}
    if(type==5 || type==6){long v=ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN).getLong(8);return v==0 || !member.equals("stage") && v==1?v:"unsupported_number";}
    if(type==3){byte[] value=string(u32(b,8),32);
      if(member.equals("stage")){
        String stage=new String(value,StandardCharsets.US_ASCII);
        return stage.matches("n_0[1-5]_(0[1-9]|10)")?stage:"unsupported_stage";
      }
      if(Arrays.equals(value,new byte[]{'0'}))return 0;
      if(Arrays.equals(value,new byte[]{'1'}))return 1;
      return "unsupported_string";
    }
    return "unsupported_kind";
  }
  public Map<String,Object> project(long rootJson) throws Exception {
    Map<String,Object> result=new LinkedHashMap<>();byte[] root=bytes(rootJson,16);int type=root[0]&255;
    if(type!=0 && type!=1)throw new IllegalStateException("marker root is not object/null");
    for(String name:List.of("MissionAutoPlay","MissionAutoPlayConfirm","MissionAutoPlayResult","mission_auto")){
      long value=type==1?find(u32(root,8),name,128):0;
      Map<String,Object> row=new LinkedHashMap<>();row.put("status",value==0?"absent":"present");
      if(value!=0){byte[] json=bytes(value,16);
        if((json[0]&255)==1){
          List<String> members=name.equals("mission_auto")?List.of("is_first_clear"):
            name.equals("MissionAutoPlay")?List.of("autoplay","stage"):List.of("autoplay");
          for(String member:members){long child=find(u32(json,8),member,32);row.put(member,child==0?"absent":scalar(child,member));}
        }else row.put("value_kind",json[0]&255);
      }
      result.put(name,row);
    }
    verify();return result;
  }
  public int readCount(){return reads.size();}
  /** Public CDN header only; caller must prove its context owner independently. */
  public Map<String,Object> projectCdnHeader(long rootJson) throws Exception {
    Map<String,Object> result=new LinkedHashMap<>();byte[] root=bytes(rootJson,16);
    if((root[0]&255)!=1)throw new IllegalStateException("CDN header is not an object");
    long object=u32(root,8);
    for(String name:List.of("stamp","cnt","size")) {
      long value=find(object,name,8);
      if(value==0)throw new IllegalStateException("CDN header member absent");
      byte[] json=bytes(value,16);int type=json[0]&255;
      if(type!=5 && type!=6)throw new IllegalStateException("CDN header member is not integer");
      long number=ByteBuffer.wrap(json).order(ByteOrder.LITTLE_ENDIAN).getLong(8);
      if(number<0)throw new IllegalStateException("CDN header integer outside diagnostic range");
      result.put(name,number);
    }
    long items=find(object,"items",8);
    if(items==0)throw new IllegalStateException("CDN header items absent");
    byte[] json=bytes(items,16);int type=json[0]&255;long container=u32(json,8),count;
    if(type==1)count=u32(bytes(container,12),8);
    else if(type==2) {
      byte[] vector=bytes(container,12);long begin=u32(vector,0),end=u32(vector,4),capacity=u32(vector,8);
      if(begin>end || end>capacity || (end-begin)%16!=0)throw new IllegalStateException("invalid CDN items vector");
      count=(end-begin)/16;
    } else throw new IllegalStateException("CDN items not object/array");
    if(count>256)throw new IllegalStateException("CDN item count exceeds bound");
    result.put("item_count",count);verify();return result;
  }
  public void verify() throws Exception {
    for(Read r:reads)if(!Arrays.equals(r.bytes,reader.read(r.address,r.bytes.length)))
      throw new IllegalStateException("marker memory changed; discard snapshot");
  }
}
