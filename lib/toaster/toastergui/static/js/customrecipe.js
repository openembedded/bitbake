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
      var targetPkg = $(this).data();

       checkPackageDeps(targetPkg, function(pkgData){
         if (targetPkg.directive === 'add'){
           /* If we're adding a package we may need to show the modal to advise
            * on dependencies for this package.
            */
           if (pkgData.unsatisfied_dependencies.length === 0){
             addRemovePackage(targetPkg);
           } else {
             showPackageDepsModal(targetPkg, pkgData);
           }
         } else if (targetPkg.directive === 'remove') {
           if (pkgData.reverse_dependencies.length === 0){
             addRemovePackage(targetPkg);
           } else {
             showPackageReverseDepsModal(targetPkg, pkgData);
           }
           }
        });
    });
  });

  function checkPackageDeps(targetPkg, doneCb){
    $.ajax({
        type: 'GET',
        url: targetPkg.packageUrl,
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

  function showPackageDepsModal(targetPkg, pkgData){
    var modal = $("#package-deps-modal");
    var depsList = modal.find("#package-add-dep-list");
    var deps = pkgData.unsatisfied_dependencies;

    modal.find(".package-to-add-name").text(targetPkg.name);

    depsList.text("");

    for (var i in deps){
      var li = $('<li></li>').text(deps[i].name);
      li.append($('<span></span>').text(" ("+
            deps[i].size_formatted+")"));
      depsList.append(li);
    }

    modal.find("#package-deps-total-size").text(
      pkgData.unsatisfied_dependencies_size_formatted);

    targetPkg.depsAdded = deps;

    addPkgDepsModalBtn.data(targetPkg);
    modal.modal('show');
  }

  addPkgDepsModalBtn.click(function(e){
    e.preventDefault();

    addRemovePackage($(this).data(), null);
  });

  function showPackageReverseDepsModal(targetPkg, pkgData){
    var modal = $("#package-reverse-deps-modal");
    var depsList = modal.find("#package-reverse-dep-list");
    var deps = pkgData.reverse_dependencies;

    modal.find(".package-to-rm-name").text(targetPkg.name);

    depsList.text("");

    for (var i in deps){
      var li = $('<li></li>').text(deps[i].name);
      li.append($('<span></span>').text(" ("+
            deps[i].size_formatted+")"));
      depsList.append(li);
    }

    modal.find("#package-reverse-deps-total-size").text(
      pkgData.reverse_dependencies_size_formatted);

    rmdPkgReverseDepsModalBtn.data(targetPkg);
    modal.modal('show');
  }

  rmdPkgReverseDepsModalBtn.click(function(e){
    e.preventDefault();

    addRemovePackage($(this).data(), null);
  });


  function addRemovePackage(targetPkg, tableParams){
    var method;
    var msg = "You have ";

    var btnCell = $("#package-btn-cell-" + targetPkg.id);
    var inlineNotify = btnCell.children(".inline-notification");

    if (targetPkg.directive === 'add') {
      method = 'PUT';
      /* If the package had dependencies also notify that they were added */
      if (targetPkg.hasOwnProperty('depsAdded') &&
        targetPkg.depsAdded.length > 0) {

        msg += "added ";
        msg += "<strong>" + (targetPkg.depsAdded.length + 1) + "</strong>";
        msg += " packages to " + ctx.recipe.name + ": ";
        msg += "<strong>" + targetPkg.name + "</strong> and its dependencies";

        for (var i in targetPkg.depsAdded){
          var dep = targetPkg.depsAdded[i];

          msg += " <strong>" + dep.name + "</strong>";

          /* Add any cells currently in view to the list of cells which get
           * an inline notification inside them and which change add/rm state
           */
          var depBtnCell = $("#package-btn-cell-" + dep.pk);
          btnCell = btnCell.add(depBtnCell);

          inlineNotify = inlineNotify.add(
            depBtnCell.children(".inline-notification"));
        }

        inlineNotify.text(
          (targetPkg.depsAdded.length + 1) + " packages added");

      } else {
        msg += "added <strong>1</strong>";
        msg += " package to " + ctx.recipe.name + ": ";
        msg += "<strong>" + targetPkg.name + "</strong>";
        inlineNotify.text("1 package added");
      }

    } else if (targetPkg.directive === 'remove') {
      method = 'DELETE';
      msg += "removed 1 package from "+ctx.recipe.name+":";
      msg += ' <strong>' + targetPkg.name + '<strong>';
      inlineNotify.text("1 package removed");
    } else {
      throw("Unknown package directive: should be add or remove");
    }

    $.ajax({
        type: method,
        url: targetPkg.packageUrl,
        headers: { 'X-CSRFToken' : $.cookie('csrftoken')},
        success: function(data){
          if (data.error !== 'ok'){
            console.warn(data.error);
            return;
          }

          libtoaster.showChangeNotification(msg);

          /* do the in-cell/inline notification to swap buttoms from add to
           * remove
           */
          btnCell.children("button").fadeOut().promise().done(function(){
            inlineNotify.fadeIn().delay(500).fadeOut(function(){
              if (targetPkg.directive === 'add')
                btnCell.children("button[data-directive=remove]").fadeIn();
              else
                btnCell.children("button[data-directive=add]").fadeIn();
            });
          });

          /* Update the total num packages */
          $.ajax({
            type: "GET",
            url: ctx.recipe.xhrPackageListUrl,
            headers: { 'X-CSRFToken' : $.cookie('csrftoken')},
            success: function(data){
              console.log(data);
              $("#total-num-packages").text(data.total);
              $("#total-size-packages").text(data.total_size_formatted);
            }
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
