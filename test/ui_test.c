/* MS20XXL UI test through the wrapper: the header buttons, the pop-up lists' engine-owned open flags, the data
 * wheel on a pop-up field's value and a patch cable, as MPC drives them (setParameter, processReplacing, automate).
 * Built and run by test/run_tests.sh against the plugin's generated params.h; scaffolding from mpc-vst-plugins' host_test.c. */

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <pthread.h>
#include "params.h"
typedef struct AEffect AEffect;
typedef intptr_t (*cb)(AEffect*,int32_t,int32_t,intptr_t,void*,float);
struct AEffect { int32_t magic; intptr_t (*d)(AEffect*,int32_t,int32_t,intptr_t,void*,float);
 void*p; void (*setP)(AEffect*,int32_t,float); float (*getP)(AEffect*,int32_t);
 int32_t np,npar,ni,no,flags; intptr_t r1,r2; int32_t a,b,c; float io; void*obj,*user; int32_t uid,ver;
 void (*pr)(AEffect*,float**,float**,int32_t); void*pdr; char f[56]; };
typedef struct { int32_t type,byteSize,deltaFrames,flags,noteLength,noteOffset; unsigned char m[4]; char x[4]; } ME;
typedef struct { int32_t n; intptr_t r; void* ev[2]; } EV;
extern AEffect* VSTPluginMain(cb);

static int automated[NPARAMS > 0 ? NPARAMS : 1], fails, updates;   /* updates: audioMasterUpdateDisplay calls */
static double ti[16];                    /* VstTimeInfo: [3] ppqPos, [4] tempo, flags = ((int32_t *)&ti[8])[5] */
static int32_t ti_flags = 1 << 10;       /* tempo valid; transport_tests() adds playing (1 << 1) and ppq valid (1 << 9) */
static intptr_t host(AEffect*e,int32_t op,int32_t i,intptr_t v,void*p,float o){
    if (op == 0 && i >= 0 && i < NPARAMS) { automated[i]++; }
    if (op == 42) updates++;
    if (op == 7) { ti[4] = 120.0; ((int32_t*)&ti[8])[5] = ti_flags; return (intptr_t)ti; }
    return 0;
}


#define CK(c,...) do{ printf("%s ",(c)?"ok  ":"FAIL"); printf(__VA_ARGS__); printf("\n"); if(!(c)) fails++; }while(0)
static void run(AEffect *a, int blocks){ float L[128],R[128],*o[2]={L,R}; for(int k=0;k<blocks;k++) a->pr(a,0,o,128); }
static int fp(const char*k){ for(int i=0;i<NPARAMS;i++) if(!strcmp(PARAMS[i].key,k)) return i; printf("no %s\n",k); exit(1); }
static float g(AEffect*a,const char*k){ return a->getP(a,fp(k)); }
int main(){ AEffect*a=VSTPluginMain(host); a->d(a,12,0,1,0,0); run(a,50);
  CK(g(a,"in_sec")<0.5f,"overview: in_sec 0");
  a->setP(a,fp("go_seq"),1); run(a,50);
  CK(g(a,"view")>0.7f && g(a,"in_sec")>0.5f,"go_seq: view sequencer, in_sec 1");
  a->setP(a,fp("pop_seq_sync"),1); run(a,50);
  CK(g(a,"pop_seq_sync")>0.5f,"arrow opens the CLOCK SYNC list");
  a->setP(a,fp("seq_sync"),3.0f/11); run(a,50);
  CK(g(a,"pop_seq_sync")<0.5f,"a pick closes the list");
  a->setP(a,fp("pop_seq_sync"),1); run(a,50);
  automated[fp("pop_seq_sync")]=0;
  a->setP(a,fp("nav_prev"),1); run(a,50);
  CK(g(a,"pop_seq_sync")<0.5f && automated[fp("pop_seq_sync")]>0,"a page change closes the open list and tells the host");
  CK(g(a,"in_sec")>0.5f,"still in a section after <");
  float v=g(a,"view"); a->setP(a,fp("nav_next"),1); run(a,50); a->setP(a,fp("nav_next"),0); run(a,50);
  CK(fabsf(g(a,"view")-v-1.0f/8)<0.01f,"one > press steps exactly one page");
  a->setP(a,fp("nav_zoom"),1); run(a,50);
  CK(g(a,"in_sec")<0.5f,"OVERVIEW: in_sec 0, nav hidden");
  /* wheel/Q-Link on the field: it is bound to the value itself; six wheel clicks step six divisions */
  a->setP(a,fp("seq_sync"),0); run(a,5);
  for(int k=0;k<6;k++){ a->setP(a,fp("seq_sync"),g(a,"seq_sync")+0.01f); }
  CK(fabsf(g(a,"seq_sync")*11-6)<0.05f,"six data wheel clicks on CLOCK SYNC step six (%.2f)", g(a,"seq_sync")*11);
  /* patching by pages, as MPC drives it: tiles are trigger buttons like the overview's, every tap asks for a redraw */
  CK(g(a,"pk")<0.01f && g(a,"pk_t")<0.01f,"overview: no patch step, no jack tiles");
  a->setP(a,fp("go_patch"),1); run(a,50);
  CK(fabsf(g(a,"pk")*4-1)<0.01f && g(a,"pk_t")>0.5f && g(a,"pk_c")<0.5f,"patch page: step 1, tiles shown, no cancel");
  int upd=updates; automated[fp("pk")]=0;
  a->setP(a,fp("tap_mg_tri"),1); run(a,50);
  CK(fabsf(g(a,"pk")*4-2)<0.01f && g(a,"pk_c")>0.5f,"MG TRI tapped: step 2 (pick an input), cancel shown");
  CK(updates>upd,"a jack tap asks the host to redraw (like a page tile)");
  CK(automated[fp("pk")]>0,"and the host is told pk moved");
  a->setP(a,fp("tap_mg_tri"),0); run(a,10);
  a->setP(a,fp("tap_total"),1); run(a,50);
  CK(fabsf(g(a,"pk")*4-4)<0.01f && g(a,"pk_t")<0.5f,"TOTAL tapped: connected page, tiles hidden");
  CK(g(a,"pt_mg_tri")>0.0f,"MG TRI -> TOTAL is patched");
  a->setP(a,fp("pk_unplug"),1); run(a,50);
  CK(fabsf(g(a,"pk")*4-1)<0.01f && g(a,"pt_mg_tri")<0.01f,"UNPLUG: cable gone, back to step 1");
  /* an input first, then an output */
  a->setP(a,fp("tap_lpf_cv"),1); run(a,50);
  CK(fabsf(g(a,"pk")*4-3)<0.01f,"LPF CUTOFF tapped first: step 3 (pick an output)");
  a->setP(a,fp("tap_freq"),1); run(a,50);
  CK(fabsf(g(a,"pk")*4-3)<0.01f,"another input is ignored while an input waits");
  a->setP(a,fp("tap_eg1_out"),1); run(a,50);
  CK(fabsf(g(a,"pk")*4-4)<0.01f && g(a,"pt_eg1_out")>0.0f,"EG1 OUT tapped: connected, EG1 OUT -> LPF CUTOFF");
  a->setP(a,fp("pk_done"),1); run(a,50);
  CK(fabsf(g(a,"pk")*4-1)<0.01f && g(a,"pt_eg1_out")>0.0f,"DONE: back to step 1, cable kept");
  CK(fabsf(g(a,"cp_eg1_out_0")*9-5)<0.01f,"the cable EG1 OUT -> LPF CUTOFF is drawn on the patch panel (cp_eg1_out_0 at 5 of 10)");
  /* a tile's momentary 0 must not do anything, and a cancel works */
  a->setP(a,fp("tap_white"),1); run(a,20); a->setP(a,fp("tap_white"),0); run(a,20);
  CK(fabsf(g(a,"pk")*4-2)<0.01f,"the release (0) of a tap does nothing");
  a->setP(a,fp("pk_cancel"),1); run(a,50);
  CK(fabsf(g(a,"pk")*4-1)<0.01f && g(a,"pk_c")<0.5f,"CANCEL: back to step 1");
  /* every picture switch has at most 11 positions (the Force limit seen on PS3100XXL) */
  int big=0; for(int i=0;i<NPARAMS;i++) if(PARAMS[i].nopts>11 && strncmp(PARAMS[i].key,"pt_",3) && strcmp(PARAMS[i].key,"seq_sync") && strcmp(PARAMS[i].key,"mg_sync")) big++;
  CK(big==0,"no drawn switch over 11 positions (%d)", big);
  CK(PARAMS[fp("pk")].nopts==5,"pk has 5 steps");
  /* a preset's cable arrives as the option index of pt_<out> */
  a->setP(a,fp("pt_seq_a"),1.0f/20); run(a,50);
  CK(g(a,"pt_seq_a")>0.04f && g(a,"pt_seq_a")<0.06f,"pt_seq_a set by the host: SEQ A -> TOTAL (%.3f)", g(a,"pt_seq_a"));
  a->setP(a,fp("nav_zoom"),1); run(a,50);
  CK(g(a,"pk")<0.01f,"leaving the patch page ends the step");
  /* a list stays open when MPC re-sends the value it already has (a focus, a redraw) */
  a->setP(a,fp("go_mod"),1); run(a,50);
  a->setP(a,fp("pop_mg_sync"),1); run(a,50);
  a->setP(a,fp("mg_sync"),g(a,"mg_sync")); run(a,50);
  CK(g(a,"pop_mg_sync")>0.5f,"a re-sent value keeps the list open");
  /* the sequencer runs from the RUN switch and the step lamp moves */
  a->setP(a,fp("go_seq"),1); run(a,50);
  a->setP(a,fp("seq_run"),1); run(a,2000);
  CK(g(a,"seq_running")>0.5f,"RUN starts the sequencer");
  CK(g(a,"seq_step_lo")>0.0f || g(a,"seq_step_hi")>0.0f,"a step lamp is lit");
  a->setP(a,fp("seq_run"),0); run(a,50);
  CK(g(a,"seq_running")<0.5f,"and stops it");
  printf(fails?"FAILED\n":"PASSED\n"); return fails!=0; }
