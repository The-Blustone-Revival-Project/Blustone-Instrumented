import java.util.*;

/** Pure interpretation of caller-qualified current battle UI visibility.
 * No memory access, VM attachment, native getter, input or resource loading.
 * The caller owns exact source-backed path/allocation/parent/name and repeated
 * stability checks. This class cannot turn unqualified nodes into evidence. */
public final class NativeBattleControls {
  private NativeBattleControls() {}
  public static final List<String> NORMAL_PANEL_NAMES=List.of("PA_AUTO_ALL","PA_AUTO_DASH","PA_AUTO_OFF");
  public static final String LOCK_PANEL_NAME="PA_AUTO_LOCK";
  public static final List<String> PANEL_NAMES=List.of("PA_AUTO_ALL","PA_AUTO_DASH","PA_AUTO_OFF",LOCK_PANEL_NAME);
  public enum Mode {
    ALL(2),DASH(1),OFF(0),LOCKED(-1),ANCESTOR_HIDDEN(-1),NONE_VISIBLE(-1);
    private final int setting;
    Mode(int setting){this.setting=setting;}
    /** Display-derived setting only for the three unlocked exact panels.
     * Original ReqMonsterRefCB G9c9ae4 chooses ALL2/DASH1/OFF0. */
    public OptionalInt setting(){return setting<0?OptionalInt.empty():OptionalInt.of(setting);}
  }
  public record Visibility(String name,int effective270,int local271) {
    public Visibility {
      if(name==null||!name.matches("[A-Za-z0-9_./-]{1,96}")||
         (effective270!=0&&effective270!=1)||(local271!=0&&local271!=1)||local271>effective270)
        throw new IllegalArgumentException("Unqualified battle-control name/visibility bytes");
    }
  }
  /** Only this exact frame mode is recognized; never falls back to touch mode
   * for a malformed/misplaced controls flag. Other existing modes return false. */
  public static boolean parseMode(String[] args) {
    if(args==null)throw new IllegalArgumentException("Missing battle-control arguments");
    boolean requested=false;
    for(int i=0;i<args.length;i++) {
      String value=args[i];if(value==null)throw new IllegalArgumentException("Null battle-control argument");
      if(!value.startsWith("--episode-controls"))continue;
      if(i!=1||!value.equals("--episode-controls")||requested)
        throw new IllegalArgumentException("Misplaced or unknown battle-control mode");
      requested=true;
    }
    if(requested&&(args.length!=3||!args[2].equals("--frame")))
      throw new IllegalArgumentException("Episode controls requires only --frame");
    return requested;
  }
  /** Ancestors must be the complete adjacent qualified root-to-parent chain,
   * not a list of guessed interesting names. The first node's outside-parent
   * state is unknown; every subsequent parent relation must already be proved
   * by the caller. This checks byte semantics, never native owner identity.
   * SetVisible G7882a0 writes271=(argument==0); InvalidateVisible G78891e sets
   * effective270=parent.effective270|local271. DrawAll skips effective hidden. */
  private static Visibility checkedParent(List<Visibility> ancestors) {
    if(ancestors==null||ancestors.isEmpty()||ancestors.size()>32)
      throw new IllegalArgumentException("Bounded complete battle-control ancestry required");
    Visibility previous=null;
    for(Visibility ancestor:ancestors) {
      if(ancestor==null)throw new IllegalArgumentException("Missing battle-control ancestor");
      if(previous!=null&&ancestor.effective270()!=(previous.effective270()|ancestor.local271()))
        throw new IllegalStateException("Battle-control ancestry visibility changed or is inconsistent");
      previous=ancestor;
    }
    return previous;
  }
  /** Actual FC UI has separate AUTO_TOGGLE and AUTO_LOCK parents. Each supplied
   * ancestry must be independently qualified; caller also proves shared root
   * identity/stability. No four-sibling or common-parent assumption is made. */
  public static Mode classifyQualified(List<Visibility> autoAncestors,List<Visibility> panels,
      List<Visibility> lockAncestors,Visibility lockPanel) {
    Visibility autoParent=checkedParent(autoAncestors),lockParent=checkedParent(lockAncestors);
    if(panels==null||panels.size()!=3||lockPanel==null||!LOCK_PANEL_NAME.equals(lockPanel.name()))
      throw new IllegalArgumentException("Three exact normal panels and separate lock panel required");
    Map<String,Visibility> byName=new HashMap<>();
    for(Visibility panel:panels) {
      if(panel==null||!NORMAL_PANEL_NAMES.contains(panel.name())||byName.putIfAbsent(panel.name(),panel)!=null)
        throw new IllegalArgumentException("Exact distinct current battle-control panels required");
      if(panel.effective270()!=(autoParent.effective270()|panel.local271()))
        throw new IllegalStateException("Battle-control panel visibility changed or is inconsistent");
    }
    if(lockPanel.effective270()!=(lockParent.effective270()|lockPanel.local271()))
      throw new IllegalStateException("Battle-control lock visibility changed or is inconsistent");
    String shown=null;
    for(String name:NORMAL_PANEL_NAMES)if(byName.get(name).effective270()==0) {
      if(shown!=null)throw new IllegalStateException("Multiple current battle-control panels are visible");shown=name;
    }
    if(lockPanel.effective270()==0) {
      if(shown!=null)throw new IllegalStateException("Lock and normal battle-control panels are both visible");
      return Mode.LOCKED;
    }
    if(shown==null)return autoParent.effective270()!=0||lockParent.effective270()!=0?Mode.ANCESTOR_HIDDEN:Mode.NONE_VISIBLE;
    return switch(shown) {
      case "PA_AUTO_ALL" -> Mode.ALL;
      case "PA_AUTO_DASH" -> Mode.DASH;
      case "PA_AUTO_OFF" -> Mode.OFF;
      default -> throw new IllegalStateException("Unknown current battle-control panel");
    };
  }
}
