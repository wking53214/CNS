#!/bin/bash
# Proof 3 queue: phase A (control, no reuse: 03, 02, 01) then phase B (all twenty, oldest first, with suite reuse),
# ONE Warden run at a time, the final pinned circuit (CNS v2.2.0 install file), no drafter, no finisher.
#
# Start:   setsid nohup bash proof3/scripts/run_all.sh > proof3/logs/queue.out 2> proof3/logs/queue.err
# (see the setup report for the exact line). Resume after a restart: run the same line again. The script
#   - skips any run whose END line is already in records/PROGRESS.txt,
#   - for a run with a START line and no END line (the run was killed): if its rc file is non-empty the run actually
#     finished, so only the END line is written; otherwise the old record files are copied to <n>.interruptedK.<ext>
#     and truncated (never deleted), a NEW target clone <n>-<sha7>.retryK is created beside the old one, and the run
#     is repeated there,
#   - stops cleanly BEFORE a run (never in the middle of one) when less than 3 GB is free on /, writing a STOP line,
#   - refuses to start while another copy of itself holds records/queue.lock,
#   - never deletes anything.
# Records: records/<A|B>/<n>.{json,err,rc,start,end,before_status,after_status,held_files,target,receipt.json}.
# Progress: records/PROGRESS.txt  ("START|END <phase> <n> <sha7> [rc=<rc>] <epoch seconds> [target=<dir>]").
# records/ALL.done is created only when every one of the 23 runs has an END line.
set -u
S=/tmp/claude-0/-home-user/f6a28526-97bd-5e48-a511-1959d5dd9622/scratchpad
P=$S/proof5
STACK=$P/stack
CNS=$P/cns
VENV=$P/venv
REC=$P/records
PROG=$REC/PROGRESS.txt
LIST=$S/falsifier/scripts/commits.txt
REFREPO=$S/falsifier/ref-ghost_tools
MIN_KB=$((3 * 1024 * 1024))

mkdir -p $REC/A $REC/B $P/logs $P/chronicleA $P/chronicleB $P/targetsA $P/targetsB
touch $PROG
exec 9>>$REC/queue.lock
if ! flock -n 9; then
  echo "QUEUE already running (lock held), exiting $(date +%s)" >> $PROG
  exit 0
fi

export PATH=$VENV/bin:$PATH
export VIRTUAL_ENV=$VENV
export PYTHONPATH=$STACK/WARDEN:$STACK/JUDGE:$CNS
unset CLAIM_COMMIT CLAIM_REPO

lookup() { # n -> sets SHA7 SHA PARENT
  local line
  line=$(awk -v n="$1" '$1==n {print $2, $3, $4}' $LIST)
  SHA7=${line%% *}; line=${line#* }; SHA=${line%% *}; PARENT=${line#* }
}

avail_kb() { df --output=avail -k / | tail -1 | tr -d ' '; }

run_one() { # phase n
  local PH=$1 N=$2 T R BASE K RETRY PREV EXT
  lookup $N
  R=$REC/$PH
  BASE=$P/targets$PH/$N-$SHA7
  if grep -q "^END $PH $N " $PROG; then return 0; fi
  PREV=$(grep -c "^START $PH $N " $PROG)
  if [ "$PREV" -gt 0 ]; then
    # a run was started and has no END line
    if [ -s $R/$N.rc ]; then
      echo "END $PH $N $SHA7 rc=$(cat $R/$N.rc) $(date +%s) (recovered: the run had finished, only the END line was missing)" >> $PROG
      return 0
    fi
    K=$PREV
    for EXT in json err rc start end before_status after_status held_files target receipt.json; do
      if [ -e $R/$N.$EXT ]; then cp $R/$N.$EXT $R/$N.interrupted$K.$EXT; : > $R/$N.$EXT; fi
    done
    T=$BASE.retry$K
    while [ -e "$T" ]; do K=$((K + 1)); T=$BASE.retry$K; done
    git clone -q $REFREPO $T && git -C $T checkout -q --detach $PARENT
  else
    T=$BASE
  fi
  local HEADNOW DIRTY
  HEADNOW=$(git -C $T rev-parse HEAD); DIRTY=$(git -C $T status --porcelain | wc -l)
  { echo "head=$HEADNOW parent=$PARENT dirty_lines=$DIRTY"; git -C $T status --porcelain; } > $R/$N.before_status
  echo "$T" > $R/$N.target
  if [ "$HEADNOW" != "$PARENT" ] || [ "$DIRTY" != "0" ]; then
    echo "STOP clone-not-ready $PH $N $SHA7 target=$T $(date +%s)" >> $PROG
    return 99
  fi
  local KB; KB=$(avail_kb)
  if [ "$KB" -lt "$MIN_KB" ]; then
    echo "STOP lowdisk avail_kb=$KB before $PH $N $SHA7 $(date +%s)" >> $PROG
    return 98
  fi
  local REUSE=""
  if [ "$PH" = "B" ]; then REUSE="--reuse-chronicle-suite"; fi
  echo "START $PH $N $SHA7 $(date +%s) target=$T" >> $PROG
  date +%s.%N > $R/$N.start
  ( cd $P/scripts && python -m warden.cli tagteam -v $T \
      --stack $STACK --cns $CNS \
      --claim-commit $SHA --claim-repo $REFREPO \
      --authorize proof5-run \
      --reason "proof5 phase $PH: govern the real AI co-authored commit $SHA7 of ghost_tools through the final pinned circuit" \
      --scope code --suite-timeout 3000 \
      --receipt $R/$N.receipt.json \
      --chronicle $P/chronicle$PH $REUSE \
      > $R/$N.json 2> $R/$N.err )
  echo $? > $R/$N.rc
  date +%s.%N > $R/$N.end
  git -C $T status --porcelain > $R/$N.after_status
  { echo "head=$(git -C $T rev-parse HEAD)"; } >> $R/$N.after_status
  for d in $T/.git/warden-state/*/held; do [ -d "$d" ] && ls $d; done > $R/$N.held_files
  echo "END $PH $N $SHA7 rc=$(cat $R/$N.rc) $(date +%s)" >> $PROG
  return 0
}

ORDER="A:03 A:02 A:01"

for item in $ORDER; do
  PH=${item%%:*}; N=${item##*:}
  if grep -q "^END $PH $N " $PROG; then continue; fi
  KB=$(avail_kb)
  if [ "$KB" -lt "$MIN_KB" ]; then
    echo "STOP lowdisk avail_kb=$KB before $PH $N $(date +%s)" >> $PROG
    exit 3
  fi
  run_one $PH $N
  RC=$?
  if [ "$RC" -ne 0 ]; then exit $RC; fi
done

DONE=$(grep -c "^END " $PROG)
if [ "$DONE" -ge 3 ]; then
  date +%s > $REC/ALL.done
  echo "ALLDONE $(date +%s)" >> $PROG
fi
