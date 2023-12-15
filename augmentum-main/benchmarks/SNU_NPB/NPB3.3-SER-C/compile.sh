#!/bin/csh

mkdir -p bin

foreach benchmark ( sp bt cg ep ft is lu mg )
    foreach class ( S )
        echo "compiling $benchmark.$class. (SER-C)"
        make $benchmark CLASS=$class

        set BLD_STATUS=$status

        if ( $BLD_STATUS != 0 ) then
            exit $BLD_STATUS
        endif

        echo "done.\n"
    end
end
