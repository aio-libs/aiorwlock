----------------------------- MODULE aiorwlock ------------------------------
EXTENDS Naturals, Sequences, Integers, FiniteSets
CONSTANTS Task
ASSUME /\ Task # {}

VARIABLES RState,
          WState,
          Lock

-----------------------------------------------------------------------------
TypeOK == /\ Lock \in [Task -> {"Read", "Write", "WriteRead", "Waiting", "Finished"}]
          /\ RState >= 0
          /\ WState >= 0 /\ WState <= 2
LockInit == Lock = [t \in Task |-> "Waiting"] /\ RState = 0 /\ WState = 0
-----------------------------------------------------------------------------


Rlocked == RState > 0
Wlocked == WState > 0
Unlocked == RState = 0 /\ WState = 0

WOwn(t) == Lock[t] \in {"Write"}

RAquire(t) == \/ /\  ~Wlocked
                 /\ Lock' = [Lock EXCEPT ![t] = "Read"]
                 /\ RState' = RState + 1
                 /\ UNCHANGED WState
                 /\ Lock[t] \in {"Waiting"}
              \/ /\ WOwn(t)
                 /\ Lock' = [Lock EXCEPT ![t] = "WriteRead"]
                 /\ RState' = RState + 1
                 /\ UNCHANGED WState

WAquire(t) == /\ Unlocked
              /\ Lock' = [Lock EXCEPT ![t] = "Write"]
              /\ WState' = WState + 1
              /\ UNCHANGED RState
              /\ Lock[t] \in {"Waiting"}


RRelease(t) == \/ /\ Rlocked /\ Lock[t] = "Read"
                  /\ RState' = RState - 1 /\ Lock' = [Lock EXCEPT ![t] = "Finished"]
                  /\ UNCHANGED WState
               \/ /\ Rlocked /\ Lock[t] = "WriteRead"
                  /\ RState' = RState - 1 /\ Lock' = [Lock EXCEPT ![t] = "Write"]
                  /\ UNCHANGED WState

WRelease(t) == \/ /\ Wlocked /\ Lock[t] = "Write"
                  /\ WState' = WState - 1 /\ Lock' = [Lock EXCEPT ![t] = "Finished"]
                  /\ UNCHANGED RState
               \/ /\ Wlocked /\ Lock[t] = "WriteRead"
                  /\ WState' = WState - 1 /\ Lock' = [Lock EXCEPT ![t] = "Read"]
                  /\ UNCHANGED RState


(* Allow infinite stuttering to prevent deadlock. *)
Finished == /\ \A t \in Task: Lock[t] = "Finished"
            /\ UNCHANGED <<RState, WState, Lock>>
-----------------------------------------------------------------------------

Next == \E t \in Task: RAquire(t) \/ WAquire(t) \/ RRelease(t) \/ WRelease(t) \/ Finished

Spec == LockInit /\ [][Next]_<<RState, WState, Lock>>


LockInv ==
    \A t1 \in Task : \A t2 \in (Task \ {t1}): ~
        (/\ Lock[t1] \in {"Write", "WriteRead"}
         /\ Lock[t2] \in {"Read", "Write", "WriteRead"})
-----------------------------------------------------------------------------

THEOREM Spec => [](TypeOK /\ LockInv)

=============================================================================

