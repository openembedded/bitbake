"use strict";

function customRecipePageInit(ctx) {

  var urlParams = libtoaster.parseUrlParams();
  var customiseTable = $("#selectpackagestable");
  var addPkgDepsModalBtn = $("#add-package-deps-modal-btn");
  var rmdPkgReverseDepsModalBtn = $("#rm-package-reverse-deps-modal-btn");

  if (urlParams.hasOwnProperty('notify') && urlParams.notify === 'new'){
    $("#image-created-notification").show();
  }

  customiseTable.on('table-done', function(e, total){
    /* Table is done so now setup the click handler for the package buttons */
    $(".add-rm-package-btn").click(function(e){
      e.preventDefault();
      var pkgBtnData = $(this).data();

       checkPackageDeps(pkgBtnData, function(pkgData){
         if (pkgBtnData.directive === 'add'){
           /* If we're adding a package we may need to show the modal to advise
            * on dependencies for this package.
            */
           if (pkgData.unsatisfied_dependencies.length === 0){
             addRemovePackage(pkgBtnData);
           } else {
             showPackageDepsModal(pkgBtnData, pkgData);
           }
         } else if (pkgBtnData.directive === 'remove') {
           if (pkgData.reverse_dependencies.length === 0){
             addRemovePackage(pkgBtnData);
           } else {
             showPackageReverseDepsModal(pkgBtnData, pkgData);
           }
           }
        });
    });
  });

  function checkPackageDeps(pkgBtnData, doneCb){
    $.ajax({
        type: 'GET',
        url: pkgBtnData.packageUrl,
        headers: { 'X-CSRFToken' : $.cookie('csrftoken')},
        success: function(data){
          if (data.error !== 'ok'){
            console.warn(data.error);
            return;
          }
          doneCb(data);
        }
    });
  }

  function showPackageDepsModal(pkgBtnData, pkgData){
    var modal = $("#package-deps-modal");
    var depsList = modal.find("#package-add-dep-list");
    var deps = pkgData.unsatisfied_dependencies;

    modal.find(".package-to-add-name").text(pkgBtnData.name);

    depsList.text("");

    for (var i in deps){
      var li = $('<li></li>').text(deps[i].name);
      li.append($('<span></span>').text(" ("+
            deps[i].size_formatted+")"));
      depsList.append(li);
    }

    modal.find("#package-deps-total-size").text(
      pkgData.unsatisfied_dependencies_size_formatted);

    addPkgDepsModalBtn.data(pkgBtnData);
    modal.modal('show');
  }

  addPkgDepsModalBtn.click(function(e){
    e.preventDefault();

    addRemovePackage($(this).data(), null);
  });

  function showPackageReverseDepsModal(pkgBtnData, pkgData){
    var modal = $("#package-reverse-deps-modal");
    var depsList = modal.find("#package-reverse-dep-list");
    var deps = pkgData.reverse_dependencies;

    modal.find(".package-to-rm-name").text(pkgBtnData.name);

    depsList.text("");

    for (var i in deps){
      var li = $('<li></li>').text(deps[i].name);
      li.append($('<span></span>').text(" ("+
            deps[i].size_formatted+")"));
      depsList.append(li);
    }

    modal.find("#package-reverse-deps-total-size").text(
      pkgData.reverse_dependencies_size_formatted);

    rmdPkgReverseDepsModalBtn.data(pkgBtnData);
    modal.modal('show');
  }

  rmdPkgReverseDepsModalBtn.click(function(e){
    e.preventDefault();

    addRemovePackage($(this).data(), null);
  });


  function addRemovePackage(pkgBtnData, tableParams){
    var method;
    var msg = "You have ";

    var btnCell = $("#package-btn-cell-"+pkgBtnData.package);
    var inlineNotify = btnCell.children(".inline-notification");

    if (pkgBtnData.directive === 'add') {
      method = 'PUT';
      msg += "added 1 package to "+ctx.recipe.name+":";
      inlineNotify.text("1 package added");
    } else if (pkgBtnData.directive === 'remove') {
      method = 'DELETE';
      msg += "removed 1 package from "+ctx.recipe.name+":";
      inlineNotify.text("1 package removed");
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

          libtoaster.showChangeNotification(msg);

          /* Also do the in-cell notification */
          btnCell.children("button").fadeOut().promise().done(function(){
            inlineNotify.fadeIn().delay(500).fadeOut(function(){
              if (pkgBtnData.directive === 'add')
                btnCell.children("button[data-directive=remove]").fadeIn();
              else
                btnCell.children("button[data-directive=add]").fadeIn();
            });
          });
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
