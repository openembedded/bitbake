// Create a namespace
var yocto = yocto || {};


// Utilities
yocto.utils = function() {
    return {
        document: jQuery(document),
        window: jQuery(window),
        body: jQuery('body')
    };
}();

// Links opening file browsers
yocto.files = function() {
    var links = jQuery('.file-type');
    return {
        init: function() {
            links.each(this.each);
            links.click(this.click);
        },
        each: function() {
            var form = jQuery(this.hash);
            var file = form.find('[type=file]');
            file.change(function() {
                form.trigger('submit');
            });
        },
        click: function(e) {
            var form = jQuery(this.hash);
            var file = form.find('[type=file]');
            file.trigger('click');
            e.preventDefault();
        }
    };
}();

yocto.users = function() {
    var table = jQuery('#user-list');
    return {
        init: function() {
            this.permissions.init();
        },
        permissions: {
            init: function() {
                var inputs = table.find('[type=checkbox]');
                inputs.removeAttr('disabled').removeAttr('checked');
                inputs.click(this.click);
            },
            click: function() {
                var checkbox = jQuery(this);
                var siblings = checkbox.parents('tr').find('[name=' + this.name + ']');
                var chain = jQuery('[class^="' + this.className + '"]');

                if (checkbox.is(':checked')) {
                    siblings.removeAttr('checked');
                    chain.prop('checked', true);
                    chain.prop('disabled', true);
                    checkbox.prop('disabled', false);
                }
                else {
                    siblings.removeAttr('disabled').removeAttr('checked');
                }
            }
        }
    };
}();

yocto.branches = function() {
    var modal = jQuery('#branchModal');
    var triggers = jQuery('a.branchModal');
    var branches = modal.find('table a');
    var current = triggers.filter(':first');
    return {
        init: function() {
            triggers.click(this.click);
            branches.click(this.close);
        },
        click: function(e) {
            current = jQuery(this);
            modal.modal('show');
        },
        close: function() {
            current.text(this.text);
            modal.modal('hide');
        }
    };
}();

yocto.dependencies = function() {
    var images = jQuery('.dependencies-graph');
    var table = jQuery('.dependencies-table');
    var input = jQuery('#recommended-show');
    return {
        init: function() {
            input.removeAttr('checked');
            input.click(this.click);
            images.hover(this.in, this.out);
        },
        click: function() {
            if (input.is(':checked')) {
                images.addClass(this.id);
                table.addClass(this.id);
            }
            else {
                images.removeClass(this.id);
                table.removeClass(this.id);
            }
        },
        in: function() {
            table.addClass('hover');
        },
        out: function() {
            table.removeClass('hover');
        }
    }
}();

$('.dropdown-toggle').dropdown();
$('.popover-toggle').popover();
$('.alert').alert();

// Initialise all
yocto.init = function() {
    yocto.files.init();
    yocto.users.init();
    yocto.dependencies.init();
    yocto.branches.init();
}();


$(document).ready(function() {
    /*
     * Table filtering.
     *
     */
    // Enable table filtering using the search input
    /*$('.filter').on('keyup', function() {
        var $this = $(this);
        var target = $this.attr('data-filter');
        var filter = $this.val().toLowerCase();
        if (target) {
            // Retrieve array of td's that this input provides filtering for
            var candidates = $('td[data-filter=' + target + ']');
            candidates.each(function() {
                if (filter) {
                    var innerText = $(this).text().toLowerCase();
                    if (innerText.indexOf(filter) === -1) {
                        $(this).closest('tr').hide();
                    }
                } else {
                    // Restore hidden rows
                    $(this).closest('tr').show();
                }
            });
        }
    });*/

    /*
     * Table sorting
     *
     */
    // Init tablesorter plugin
    //$('.tablesorter').tablesorter();

    // Append sort icon to each table header
    //$('.tablesorter th').append('&nbsp;<i class="sort icon-sort"></i>');

    // Update/change sort icon (up or down) when sort happens
    $('.tablesorter').on('sortEnd', function() {
        $(this).find('th').each(function() {
            var $this = $(this);
            // sort icon for this th
            var $icon = $(this).find('.sort');
            // switch icon depending on current sort status
            if ($this.hasClass('headerSortUp')) {
                $icon.attr('class', 'sort icon-caret-up');
            } else if ($this.hasClass('headerSortDown')) {
                $icon.attr('class', 'sort icon-caret-down');
            } else {
                $icon.attr('class', 'sort');
            }
        });
    });

    /*
     * Collapse plugin.
     *
     */
    $('.collapse').on('hide', function() {
        $(this).siblings('[class="icon-caret-down"]').attr('class', 'icon-caret-right');
        $(this).parent().find('[class="icon-caret-down"]').attr('class', 'icon-caret-right');
    });
    $('.collapse').on('show', function() {
        $(this).siblings('[class="icon-caret-right"]').attr('class', 'icon-caret-down');
        $(this).parent().find('[class="icon-caret-right"]').attr('class', 'icon-caret-down');
    });

    /*
     * PrettyPrint plugin.
     *
     */
    // Init
    prettyPrint();

    /*
     * Misc
     *
     */
    // Prevent clicking on muted (disabled) link
    /* $('a.muted, div.muted').click(function() {
        return false;

    // Show tooltip for disabled links
    }).tooltip({
        title: 'Link is not functional in this demo.',
        delay: {
            show: 400,
            hide: 0
        }
    });*/

    /*$('table').tooltip({
        title: 'Sorting disabled',
        delay: {
            show: 400,
            hide: 0
        }
    });*/

    $('.info').tooltip();

    // Box functions on project-build page
    $('.box-close').click(function() {
        $(this).closest('.box').hide(100);
    });

    $('[name=highlight-row]').click(function() {
        var parent = jQuery(this).parents('tr:first');
        if (this.type == 'radio') {
            parent.siblings().removeClass('selected');
        }
        if (this.checked) {
            parent.addClass('selected');
        }
        else {
            parent.removeClass('selected');
        }
    });

    /*$('a.error, a.warning').each(function() {
        this.href = 'all-tasks.html?filter=' + this.className;
    });

    $('.icon-minus-sign.warning').each(function() {
        jQuery(this).next('a').attr('href', 'all-tasks.html?filter=warning');
    });

    $('.icon-minus-sign.error').each(function() {
        jQuery(this).next('a').attr('href', 'all-tasks.html?filter=error');
    });
    
	$('#failedbuild').each(function() {
    	this.href = '#';
    });

    if (location.href.search('filter=') > -1) {
        var filter = location.href.split('filter=')[1];
        var cells = jQuery('.' + filter);
        //jQuery('tr').hide();
        $("tbody > tr").hide();
        cells.each(function() {
        	if($(this).is('a')) {
            	jQuery(this).parents('tr').show();
            }
        });
    }*/

    // Prevent invalid links from jumping page scroll
    $('a[href=#]').click(function() {
        return false;
    });

    jQuery('#project-project-files-search-results').each(function() {
        jQuery('input.' + this.id).val(jQuery(this).text());
    });

    jQuery('.bar.building').each(function() {
        var bar = jQuery(this);
        bar.animate({
            width: '100%'
        }, {
            duration: parseInt(bar.attr('data-time')),
            complete: function() {
                location.href = bar.attr('data-url');
            }
        });
    });

    jQuery('#project-build-packages').each(function() {
        var link = this;
        var size = jQuery('[href=#size]');
        var dependencies = jQuery('[href=#dependencies]');
        size.click(function() {
            link.href = 'project-build-packages.html';
        });
        dependencies.click(function() {
            link.href = 'project-build-packages-dependencies.html';
        });
    });

    if (location.href.search('tab') !== -1) {
        jQuery('[href=#' + location.href.split('tab=')[1] + ']').trigger('click');
    }

    jQuery('.tree a').each(function() {
        var link = jQuery(this);
        var parent = link.parents('li:first');
        var child = parent.find('ul');
        var prev = link.prev('i:first');
        link.click(function() {
            if (prev.attr('class') == 'icon-caret-down') {
                child.slideUp('fast');
                prev.attr('class', 'icon-caret-right');
            }
            else {
                child.slideDown('fast');
                prev.attr('class', 'icon-caret-down');
            }
            return false;
        });
    });

    /*jQuery('#nav').each(function() {
        var links = jQuery(this).find('a');
        var split = location.href.split('/');
        var file = split[split.length - 1].split('?')[0];
        if (file == 'project-build-packages-busybox.html') {
            file = 'project-build-packages.html';
        }
        else if (file == 'project-build-packages-dependencies.html') {
            file = 'project-build-packages.html';
        }
        links.filter('[href="' + file + '"]').parent().addClass('active');
    });*/
    
    //Belen's additions
    
    //make help tooltip and popovers work on click, mutually exclusive and dismiss them when clicking outside their area
    //from http://fuzzytolerance.info/blog/quick-hack-one-bootstarp-popover-at-a-time/
    //one problem: clicking inside the tooltip or popover should not dismiss it, but it currently does
    
    // Global variables - cringe
    var visibleTooltip;
    
    //show help information   
    $(".get-help").tooltip({ container: 'body', html: true, delay: {show: 300} /* trigger: 'hover'*/});
    
	//show help for task outcome on hover
	$(".hover-help").hide();
	$("tr").hover(function () {
		$(this).find(".hover-help").show();
	});
	$("tr").mouseleave(function () {
		$(this).find(".hover-help").hide();
	});	
    
	/*
	//only allow one tooltip at a time
	$(".get-help").on('click', function(e) {
    	// don't fall through
    	e.stopPropagation();
    	var $this = $(this);
    	// check if the one clicked is now shown
    	if ($this.data('tooltip').tip().hasClass('in')) {
        	// if another was showing, hide it
        	visibleTooltip && visibleTooltip.tooltip('hide');
        	// then store the current tooltip
        	visibleTooltip = $this;
    	} else {
        	// if it was hidden, then nothing must be showing
        	visibleTooltip = '';
    	}
    	// dismiss tooltips when you click outside them
    	$('body').on("click", function (e) {
    		var $target = $(e.target),
    		inTooltip = $(e.target).closest('.popover').length > 0
			//hide only if clicked on button or inside popover
    		if (!inTooltip) {
    			visibleTooltip.tooltip('hide');
    			visibleTooltip = '';
    		}
		});
	});
	*/
    
	// Global variables - cringe
	var visiblePopover;

	// enable popovers
	$('.depends > a , .brought_in_by > a, .recommends > a, .layer_commit > a').popover({html:true, container:'body', placement: 'left'});

    // make sure on hover elements do not disappear while the pointer is inside them 
    // buggy: doesn't work if you hover over the same popover twice in a row

	 /*$('.depends > a , .brought_in_by > a, .recommends > a, .layer_commit').popover({
		offset: 10,
		trigger: 'manual',
		animate: false,
		html: true,
		placement: 'left',
		container: 'body',
		template: '<div class="popover" onmouseover="$(this).mouseleave(function() {$(this).hide(); });"><div class="arrow"></div><div class="popover-inner"><h3 class="popover-title"></h3><div class="popover-content"><p></p></div></div></div>'

	}).click(function(e) {
		$(this).popover('show');
	});*/

	/*
	// only allow 1 tooltip at a time
	$('.get-help').on('click', function(e) {
    	// don't fall through
    	e.stopPropagation();
    	var $this = $(this);
    	// check if the one clicked is now shown
    	if ($this.data('tooltip').tip().hasClass('in')) {
        	// if another was showing, hide it
        	visibleTooltip && visibleTooltip.tooltip('hide');
        	// then store the current popover
        	visibleTooltip = $this;
    	} else {
        	// if it was hidden, then nothing must be showing
        	visibleToolitp = '';
    	}
	});
	*/
	
	//only allow 1 popover at a time
	$('.depends > a , .brought_in_by > a, .recommends > a, .layer_commit > a').on('click', function(e) {
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
	
	
	/*
	// hide all tooltips if any non-tooltip part of the body is clicked
	// this does not work properly: clicking the tooltip will also dismiss the tootlip
	$("body").on('click', function () {
    	$(".get-help").tooltip('hide');
    	visibleTootlip = '';
	});*/
	

	
	// hide all popovers if any non-popover part of the body is clicked
	// this does not work properly: clicking the popover will also dismiss the popover
	/*$("body").on('click', function () {
    	$('.depends > a , .brought_in_by > a, .recommends > a, .layer_commit > a').popover('hide');
    	visiblePopover = '';
	});*/
	
	//linking directly to tabs
	$(function(){
  		var hash = window.location.hash;
  		hash && $('ul.nav a[href="' + hash + '"]').tab('show');

  		$('.nav-tabs a').click(function (e) {
    		$(this).tab('show');
    		//var scrollmem = $('body').scrollTop();
    		//window.location.hash = this.hash;
    		//$('html,body').scrollTop(scrollmem);
  		});
	});


});
