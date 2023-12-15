#include <stdio.h>
#include <math.h>

typedef enum { false, true } logical;

// Auto2 verification
// this will not be touched by any optimisations done by auto2 to keep verification and
// benchmark separated
//
// it is only inteded to work for input class S
void auto2_verify(char *Class, double dt, double xce[5], double xcr[5], double xci) {

    double xcrref[5], xceref[5], xciref;
    double xcrdif[5], xcedif[5], xcidif;
    double epsilon, dtref = 0.0;
    int m;
    logical verified;

    if (*Class != 'S') {
        printf("AUTO2: Invalid workload class %c used for verification.\n", *Class);
        return;
    }

    //---------------------------------------------------------------------
    // tolerance level
    //---------------------------------------------------------------------
    epsilon = 1.0e-08;

    // specify reference values for class S
    dtref = 5.0e-1;
    
    //---------------------------------------------------------------------
    // Reference values of RMS-norms of residual, for the (12X12X12) grid,
    // after 50 time steps, with  DT = 5.0e-01
    //---------------------------------------------------------------------
    xcrref[0] = 1.6196343210976702e-02;
    xcrref[1] = 2.1976745164821318e-03;
    xcrref[2] = 1.5179927653399185e-03;
    xcrref[3] = 1.5029584435994323e-03;
    xcrref[4] = 3.4264073155896461e-02;

    //---------------------------------------------------------------------
    // Reference values of RMS-norms of solution error, 
    // for the (12X12X12) grid,
    // after 50 time steps, with  DT = 5.0e-01
    //---------------------------------------------------------------------
    xceref[0] = 6.4223319957960924e-04;
    xceref[1] = 8.4144342047347926e-05;
    xceref[2] = 5.8588269616485186e-05;
    xceref[3] = 5.8474222595157350e-05;
    xceref[4] = 1.3103347914111294e-03;

    //---------------------------------------------------------------------
    // Reference value of surface integral, for the (12X12X12) grid,
    // after 50 time steps, with DT = 5.0e-01
    //---------------------------------------------------------------------
    xciref = 7.8418928865937083e+00;

    //---------------------------------------------------------------------
    // Compute the difference of solution values and the known reference values.
    //---------------------------------------------------------------------
    for (m = 0; m < 5; m++) {
        xcrdif[m] = fabs((xcr[m]-xcrref[m])/xcrref[m]);
        xcedif[m] = fabs((xce[m]-xceref[m])/xceref[m]);
    }
    xcidif = fabs((xci - xciref)/xciref);

    // ---------------------------------------------------------------------
    // Output the comparison of computed results to known cases.
    // ---------------------------------------------------------------------
    verified = fabs(dt-dtref) <= epsilon;
    if (!verified) {  
        printf("AUTO2 Verification failed.\n");
        return;
    }

    for (m = 0; m < 5; m++) {
        if (xcrdif[m] <= epsilon) {
            verified = true;
        } else { 
            verified = false;
            break;
        }
    }
    if (!verified) {  
        printf("AUTO2 Verification failed.\n");
        return;
    }

    for (m = 0; m < 5; m++) {
        if (xcedif[m] <= epsilon) {
            verified = true;
        } else { 
            verified = false;
            break;
        }
    }
    if (!verified) {  
        printf("AUTO2 Verification failed.\n");
        return;
    }

    if (xcidif <= epsilon) {
        verified = true;
    } else { 
        verified = false;
    }
    if (!verified) {  
        printf("AUTO2 Verification failed.\n");
        return;
    }

    printf("AUTO2 Verification successful.\n");
}