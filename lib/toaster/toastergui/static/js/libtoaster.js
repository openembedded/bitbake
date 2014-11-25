
/* All shared functionality to go in libtoaster object.
 * This object really just helps readability since we can then have
 * a traceable namespace.
 */
var libtoaster = (function (){

  /* makeTypeahead parameters
   * elementSelector: JQuery elementSelector string
   * xhrUrl: the url to get the JSON from expects JSON in the form:
   *  { "list": [ { "name": "test", "detail" : "a test thing"  }, .... ] }
   * xhrParams: the data/parameters to pass to the getJSON url e.g.
   *  { 'type' : 'projects' } the text typed will be passed as 'value'.
   *  selectedCB: function to call once an item has been selected one
   *  arg of the item.
   */
  function _makeTypeahead (jQElement, xhrUrl, xhrParams, selectedCB) {

    jQElement.typeahead({
        source: function(query, process){
          xhrParams.value = query;
          $.getJSON(xhrUrl, this.options.xhrParams, function(data){
            return process (data.list);
          });
        },
        updater: function(item) {
          var itemObj = this.$menu.find('.active').data('itemObject');
          selectedCB(itemObj);
          return item;
        },
        matcher: function(item) {  return ~item.name.toLowerCase().indexOf(this.query.toLowerCase()); },
        highlighter: function (item) {
          if (item.hasOwnProperty('detail'))
            /* Use jquery to escape the value as text into a span */
            return $('<span></span>').text(item.name+' '+item.detail).get(0);
          return $('<span></span>').text(item.name).get(0);
        },
        sorter: function (items) { return items; },
        xhrUrl: xhrUrl,
        xhrParams: xhrParams,
    });


    /* Copy of bootstrap's render func but sets selectedObject value */
    function customRenderFunc (items) {
      var that = this;

      items = $(items).map(function (i, item) {
        i = $(that.options.item).attr('data-value', item.name).data('itemObject', item);
        i.find('a').html(that.highlighter(item));
        return i[0];
      });

      items.first().addClass('active');
      this.$menu.html(items);
      return this;
    }

    jQElement.data('typeahead').render = customRenderFunc;
  };

  /*
   * url - the url of the xhr build */
  function _startABuild (url, project_id, targets, onsuccess, onfail) {
    var data;

    if (project_id)
      data = 'project_id='+project_id+'&targets='+targets;
    else
      data = 'targets='+targets;

    $.ajax( {
        type: "POST",
        url: url,
        data: data,
        headers: { 'X-CSRFToken' : $.cookie('csrftoken')},
        success: function (_data) {
          if (_data.error != "ok") {
            console.log(_data.error);
          } else {
            if (onsuccess != undefined) onsuccess(_data);
          }
        },
        error: function (_data) {
          console.log("Call failed");
          console.log(_data);
          if (onfail) onfail(data);
    } });
  };

  /* Get a project's configuration info */
  function _getProjectInfo(url, projectId, onsuccess, onfail){
    $.ajax({
        type: "POST",
        url: url,
        data: { project_id : projectId },
        headers: { 'X-CSRFToken' : $.cookie('csrftoken')},
        success: function (_data) {
          if (_data.error != "ok") {
            console.log(_data.error);
          } else {
            if (onsuccess != undefined) onsuccess(_data);
          }
        },
        error: function (_data) {
          console.log(_data);
          if (onfail) onfail(data);
        }
    });
  };

  return {
    reload_params : reload_params,
    startABuild : _startABuild,
    makeTypeahead : _makeTypeahead,
    getProjectInfo: _getProjectInfo,
  }
})();

/* keep this in the global scope for compatability */
function reload_params(params) {
    uri = window.location.href;
    splitlist = uri.split("?");
    url = splitlist[0], parameters=splitlist[1];
    // deserialize the call parameters
    if(parameters){
        cparams = parameters.split("&");
    }else{
        cparams = []
    }
    nparams = {}
    for (i = 0; i < cparams.length; i++) {
        temp = cparams[i].split("=");
        nparams[temp[0]] = temp[1];
    }
    // update parameter values
    for (i in params) {
        nparams[encodeURIComponent(i)] = encodeURIComponent(params[i]);
    }
    // serialize the structure
    callparams = []
    for (i in nparams) {
        callparams.push(i+"="+nparams[i]);
    }
    window.location.href = url+"?"+callparams.join('&');
}


/* Things that happen for all pages */
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
    // .btn class applied, and make sure popovers work on click, are mutually
    // exclusive and they close when your click outside their area

    $('html').click(function(e){
        $('td > a.btn').popover('hide');
    });

    $('td > a.btn').popover({
        html:true,
        placement:'left',
        container:'body',
        trigger:'manual'
    }).click(function(e){
        $('td > a.btn').not(this).popover('hide');
        // ideally we would use 'toggle' here
        // but it seems buggy in our Bootstrap version
        $(this).popover('show');
        e.stopPropagation();
    });

    // enable tooltips for applied filters
    $('th a.btn-primary').tooltip({container:'body', html:true, placement:'bottom', delay:{hide:1500}});

    // hide applied filter tooltip when you click on the filter button
    $('th a.btn-primary').click(function () {
        $('.tooltip').hide();
    });

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

    // toggle for long content (variables, python stack trace, etc)
    $('.full, .full-hide').hide();
    $('.full-show').click(function(){
        $('.full').slideDown(function(){
            $('.full-hide').show();
        });
        $(this).hide();
    });
    $('.full-hide').click(function(){
        $(this).hide();
        $('.full').slideUp(function(){
            $('.full-show').show();
        });
    });

    //toggle the errors and warnings sections
    $('.show-errors').click(function() {
        $('#collapse-errors').addClass('in');
    });
    $('.toggle-errors').click(function() {
        $('#collapse-errors').toggleClass('in');
    });
    $('.show-warnings').click(function() {
        $('#collapse-warnings').addClass('in');
    });
    $('.toggle-warnings').click(function() {
        $('#collapse-warnings').toggleClass('in');
    });
    $('.show-exceptions').click(function() {
        $('#collapse-exceptions').addClass('in');
    });
    $('.toggle-exceptions').click(function() {
        $('#collapse-exceptions').toggleClass('in');
    });

    //show warnings section when requested from the previous page
    if (location.href.search('#warnings') > -1) {
        $('#collapse-warnings').addClass('in');
    }
});
