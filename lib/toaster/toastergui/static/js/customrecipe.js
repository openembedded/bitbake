"use strict";

function customRecipePageInit(ctx) {

  var urlParams = libtoaster.parseUrlParams();
  var customiseTable = $("#selectpackagestable");

  (function notificationRequest(){
    if (urlParams.hasOwnProperty('notify') && urlParams.notify === 'new'){
      $("#image-created-notification").show();
    }
  })();

  customiseTable.on('table-done', function(e, total, tableParams){
    /* Table is done so now setup the click handler for the package buttons */
    $(".add-rm-package-btn").click(function(e){
      e.preventDefault();
      addRemovePackage($(this), tableParams);
    });
  });

  function addRemovePackage(pkgBtn, tableParams){
    var pkgBtnData = pkgBtn.data();
    var method;
    var msg = "You have ";

    if (pkgBtnData.directive == 'add') {
      method = 'PUT';
      msg += "added 1 package to "+ctx.recipe.name+":";
    } else if (pkgBtnData.directive == 'remove') {
      method = 'DELETE';
      msg += "removed 1 package from "+ctx.recipe.name+":";
    } else {
      throw("Unknown package directive: should be add or remove");
    }

    msg += ' <strong>' + pkgBtnData.name + '<strong>';

    $.ajax({
        type: method,
        url: pkgBtnData.packageUrl,
        headers: { 'X-CSRFToken' : $.cookie('csrftoken')},
        success: function(data){
          if (data.error !== 'ok'){
            console.warn(data.error);
            return;
          }
          /* Reload and Invalidate the Add | Rm package table's current data */
          tableParams.nocache = true;
          customiseTable.trigger('reload', [tableParams]);

          libtoaster.showChangeNotification(msg);
        }
    });
  }

  /* Trigger a build of your custom image */
  $(".build-custom-image").click(function(){
    libtoaster.startABuild(libtoaster.ctx.projectBuildsUrl,
      libtoaster.ctx.projectId,
      ctx.recipe.name,
      function(){
        window.location.replace(libtoaster.ctx.projectBuildsUrl);
    });
  });
}
