$(document).ready(function() {

    /*
     * PrettyPrint plugin.
     *
     */
    // Init
    prettyPrint();

    // Prevent invalid links from jumping page scroll
    $('a[href=#]').click(function() {
        return false;
    });


    /* Belen's additions */

	// turn Edit columns dropdown into a multiselect menu
	$('.dropdown-menu input, .dropdown-menu label').click(function(e) {
		e.stopPropagation();
	});

    // enable popovers in any table cells that contain an anchor with the
    // .btn class applied
	$('td > a.btn').popover({html:true, container:'body', placement:'left'});

	// enable tooltips for applied filters
	$('th a.btn-primary').tooltip({container:'body', html:true, placement:'bottom', delay:{hide:1500}});

	// enable help information tooltip
    $(".get-help").tooltip({container:'body', html:true, delay:{show:300}});

	// show help bubble only on hover inside tables
	$(".hover-help").css("visibility","hidden");
	$("th, td").hover(function () {
		$(this).find(".hover-help").css("visibility","visible");
	});
	$("th, td").mouseleave(function () {
		$(this).find(".hover-help").css("visibility","hidden");
	});

    // show task type and outcome in task details pages
    $(".task-info").tooltip({ container: 'body', html: true, delay: {show: 200}, placement: 'right' });

	// linking directly to tabs
	$(function(){
  		var hash = window.location.hash;
  		hash && $('ul.nav a[href="' + hash + '"]').tab('show');

  		$('.nav-tabs a').click(function (e) {
    		$(this).tab('show');
			$('body').scrollTop();
  		});
	});

    /* Make help tooltip and popovers work on click, mutually exclusive and dismiss them when clicking outside their area
    from http://fuzzytolerance.info/blog/quick-hack-one-bootstarp-popover-at-a-time/  */

    // Global variables - cringe
    var visibleTooltip;
    var visiblePopover;

	//only allow 1 popover at a time
	$('.depends > a , .brought_in_by > a, .layer_commit > a').on('click', function(e) {
    	// don't fall through
    	e.stopPropagation();
    	var $this = $(this);
    	// check if the one hovered over is now shown
    	if ($this.data('popover').tip().hasClass('in')) {
        	// if another was showing, hide it
        	visiblePopover && visiblePopover.popover('hide');
        	// then store the current popover
        	visiblePopover = $this;
    	} else {
        	// if it was hidden, then nothing must be showing
        	visiblePopover = '';
    	}
    	// dismiss popovers when you click outside them
    	$('body').on("click", function (e) {
    		var $target = $(e.target),
    		inPopover = $(e.target).closest('.popover').length > 0
			//hide only if clicked on button or inside popover
    		if (!inPopover) {
    			visiblePopover.popover('hide');
    			visiblePopover = '';
    		}
		});
	});

});
