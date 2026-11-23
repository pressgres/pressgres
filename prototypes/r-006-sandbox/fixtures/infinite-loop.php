<?php
/** Plugin Name: R-006 Infinite Loop */
register_activation_hook( __FILE__, static function (): void {
	r006_observe( 'loop', [ 'entered' => true ] );
	while ( true ) {
		// Exercise the wall clock and bounded CPU with a single process.
	}
} );
