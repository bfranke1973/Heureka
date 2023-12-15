#include <stdio.h>
#include <math.h>

typedef enum { false, true } logical;

// Auto2 verification
// this will not be touched by any optimisations done by auto2 to keep verification and
// benchmark separated
//
// it is only inteded to work for input class S
void auto2_verify(char *Class, double dt, double xce[5], double xcr[5]) {

    double xcrref[5], xceref[5], xcrdif[5], xcedif[5]; 
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
    dtref = 1.5e-2;

    //---------------------------------------------------------------------
    // Reference values of RMS-norms of residual.
    //---------------------------------------------------------------------
    xcrref[0] = 2.7470315451339479e-02;
    xcrref[1] = 1.0360746705285417e-02;
    xcrref[2] = 1.6235745065095532e-02;
    xcrref[3] = 1.5840557224455615e-02;
    xcrref[4] = 3.4849040609362460e-02;

    //---------------------------------------------------------------------
    // Reference values of RMS-norms of solution error.
    //---------------------------------------------------------------------
    xceref[0] = 2.7289258557377227e-05;
    xceref[1] = 1.0364446640837285e-05;
    xceref[2] = 1.6154798287166471e-05;
    xceref[3] = 1.5750704994480102e-05;
    xceref[4] = 3.4177666183390531e-05;

    //---------------------------------------------------------------------
    // Compute the difference of solution values and the known reference values.
    //---------------------------------------------------------------------
    for (m = 0; m < 5; m++) {
        xcrdif[m] = fabs((xcr[m]-xcrref[m])/xcrref[m]);
        xcedif[m] = fabs((xce[m]-xceref[m])/xceref[m]);
    }

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

    printf("AUTO2 Verification successful.\n");
}