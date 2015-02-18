"use strict"

function importLayerPageInit (ctx) {

  var layerDepBtn = $("#add-layer-dependency-btn");
  var importAndAddBtn = $("#import-and-add-btn");
  var layerNameInput = $("#import-layer-name");
  var vcsURLInput = $("#layer-git-repo-url");
  var gitRefInput = $("#layer-git-ref");
  var layerDepInput = $("#layer-dependency");
  var layerNameCtrl = $("#layer-name-ctrl");
  var duplicatedLayerName = $("#duplicated-layer-name-hint");

  var layerDeps = {};
  var layerDepsDeps = {};
  var currentLayerDepSelection;
  var validLayerName = /^(\w|-)+$/;

  $("#new-project-button").hide();

  libtoaster.makeTypeahead(layerDepInput, ctx.xhrDataTypeaheadUrl, { type : "layers", project_id: ctx.projectId, include_added: "true" }, function(item){
    currentLayerDepSelection = item;

    layerDepBtn.removeAttr("disabled");
  });


  /* We automatically add "openembedded-core" layer for convenience as a
   * dependency as pretty much all layers depend on this one
   */
  $.getJSON(ctx.xhrDataTypeaheadUrl, { type : "layers", project_id: ctx.projectId, include_added: "true" , value: "openembedded-core" }, function(layer) {
    if (layer.list.length == 1) {
      currentLayerDepSelection = layer.list[0];
      layerDepBtn.click();
    }
  });

  layerDepBtn.click(function(){
    if (currentLayerDepSelection == undefined)
      return;

    layerDeps[currentLayerDepSelection.id] = currentLayerDepSelection;

    /* Make a list item for the new layer dependency */
    var newLayerDep = $("<li><a></a><span class=\"icon-trash\" data-toggle=\"tooltip\" title=\"Delete\"></span></li>");

    newLayerDep.data('layer-id', currentLayerDepSelection.id);
    newLayerDep.children("span").tooltip();

    var link = newLayerDep.children("a");
    link.attr("href", ctx.layerDetailsUrl+String(currentLayerDepSelection.id));
    link.text(currentLayerDepSelection.name);
    link.tooltip({title: currentLayerDepSelection.tooltip, placement: "right"});

    var trashItem = newLayerDep.children("span");
    trashItem.click(function () {
      var toRemove = $(this).parent().data('layer-id');
      delete layerDeps[toRemove];
      $(this).parent().fadeOut(function (){
        $(this).remove();
      });
    });

    $("#layer-deps-list").append(newLayerDep);

    libtoaster.getLayerDepsForProject(ctx.xhrDataTypeaheadUrl, ctx.projectId, currentLayerDepSelection.id, function (data){
        /* These are the dependencies of the layer added as a dependency */
        if (data.list.length > 0) {
          currentLayerDepSelection.url = ctx.layerDetailsUrl+currentLayerDepSelection.id;
          layerDeps[currentLayerDepSelection.id].deps = data.list
        }

        /* Clear the current selection */
        layerDepInput.val("");
        currentLayerDepSelection = undefined;
        layerDepBtn.attr("disabled","disabled");
      }, null);
  });

  importAndAddBtn.click(function(){
    /* This is a list of the names from layerDeps for the layer deps
     * modal dialog body
     */
    var depNames = [];

    /* arrray of all layer dep ids includes parent and child deps */
    var allDeps = [];

    /* temporary object to use to do a reduce on the dependencies for each
     * layer dependency added
     */
    var depDeps = {};

    /* the layers that have dependencies have an extra property "deps"
     * look in this for each layer and reduce this to a unquie object
     * of deps.
     */
    for (var key in layerDeps){
      if (layerDeps[key].hasOwnProperty('deps')){
        for (var dep in layerDeps[key].deps){
          var layer = layerDeps[key].deps[dep];
          depDeps[layer.id] = layer;
        }
      }
      depNames.push(layerDeps[key].name);
      allDeps.push(layerDeps[key].id);
    }

    /* we actually want it as an array so convert it now */
    var depDepsArray = [];
    for (var key in depDeps)
      depDepsArray.push (depDeps[key]);

    if (depDepsArray.length > 0) {
      var layer = { name: layerNameInput.val(), url: "#", id: -1 };
      var title = "Layer";
      var body = "<strong>"+layer.name+"</strong>'s dependencies ("+
        depNames.join(", ")+"</span>) require some layers that are not added to your project. Select the ones you want to add:</p>";

      show_layer_deps_modal(ctx.projectId, layer, depDepsArray, title, body, false, function(selected){
        /* Add the accepted dependencies to the allDeps array */
        if (selected.length > 0){
          allDeps = allDeps.concat (selected);
        }
        import_and_add ();
      });
    } else {
      import_and_add ();
    }

    function import_and_add () {
      /* convert to a csv of all the deps to be added */
      var layerDepsCsv = allDeps.join(",");

      var layerData = {
        name: layerNameInput.val(),
        vcs_url: vcsURLInput.val(),
        git_ref: gitRefInput.val(),
        dir_path: $("#layer-subdir").val(),
        project_id: ctx.projectId,
        layer_deps: layerDepsCsv,
      };

      $.ajax({
          type: "POST",
          url: ctx.xhrImportLayerUrl,
          data: layerData,
          headers: { 'X-CSRFToken' : $.cookie('csrftoken')},
          success: function (data) {
            if (data.error != "ok") {
              show_error_message(data, layerData);
              console.log(data.error);
            } else {
              /* Success layer import now go to the project page */
              $.cookie('layer-imported-alert', JSON.stringify(data), { path: '/'});
              window.location.replace(ctx.projectPageUrl+'#/layerimported');
            }
          },
          error: function (data) {
            console.log("Call failed");
            console.log(data);
          }
      });
    }
  });

  function show_error_message(error, layerData) {

    var errorMsg = $("#import-error").fadeIn();
    var errorType = error.error;
    var body = errorMsg.children("p");
    var title = errorMsg.children("h3");
    var optionsList = errorMsg.children("ul");
    var invalidLayerRevision = $("#invalid-layer-revision-hint");
    var layerRevisionCtrl = $("#layer-revision-ctrl");

    /* remove any existing items */
    optionsList.children().each(function(){ $(this).remove(); });
    body.text("");
    title.text("");
    invalidLayerRevision.hide();
    layerNameCtrl.removeClass("error");
    layerRevisionCtrl.removeClass("error");

    switch (errorType){
      case 'hint-layer-version-exists':
        title.text("This layer already exists");
        body.html("A layer <strong>"+layerData.name+"</strong> already exists with this Git repository URL and this revision. You can:");
        optionsList.append("<li>Import <strong>"+layerData.name+"</strong> with a different revision </li>");
        optionsList.append("<li>or <a href=\""+ctx.layerDetailsUrl+error.existing_layer_version+"/\" >change the revision of the existing layer</a></li>");

        layerRevisionCtrl.addClass("error");

        invalidLayerRevision.html("A layer <strong>"+layerData.name+"</strong> already exists with this revision.<br />You can import <strong>"+layerData.name+"</strong> with a different revision");
        invalidLayerRevision.show();
        break;

      case 'hint-layer-exists-with-different-url':
        title.text("This layer already exists");
        body.html("A layer <strong>"+layerData.name+"</strong> already exists with a different Git repository URL:<p style='margin-top:10px;'><strong>"+error.current_url+"</strong></p><p>You can:</p>");
        optionsList.append("<li>Import the layer under a different name</li>");
        optionsList.append("<li>or <a href=\""+ctx.layerDetailsUrl+error.current_id+"/\" >change the Git repository URL of the existing layer</a></li>");
        duplicatedLayerName.html("A layer <strong>"+layerData.name+"</strong> already exists with a different Git repository URL.<br />To import this layer give it a different name.");
        duplicatedLayerName.show();
        layerNameCtrl.addClass("error");
        break;

      case 'hint-layer-exists':
        title.text("This layer already exists");
        body.html("A layer <strong>"+layerData.name+"</strong> already exists. You can:");
        optionsList.append("<li>Import the layer under a different name</li>");
        break;
      default:
        title.text("Error")
        body.text(data.error);
    }
  }

  function enable_import_btn (enabled) {
    var importAndAddHint = $("#import-and-add-hint");

    if (enabled) {
      importAndAddBtn.removeAttr("disabled");
      importAndAddHint.hide();
      return;
    }

    importAndAddBtn.attr("disabled", "disabled");
    importAndAddHint.show();
  }

  function check_form() {
    var valid = false;
    var inputs = $("input:required");

    for (var i=0; i<inputs.length; i++){
      if (!(valid = inputs[i].value)){
        enable_import_btn(false);
        break;
      }
    }

    if (valid)
      enable_import_btn(true);
  }

  vcsURLInput.on('input', function() {
    check_form();
  });

  gitRefInput.on('input', function() {
    check_form();
  });

  layerNameInput.on('input', function() {
    if ($(this).val() && !validLayerName.test($(this).val())){
      layerNameCtrl.addClass("error")
      $("#invalid-layer-name-hint").show();
      enable_import_btn(false);
      return;
    }

    /* Don't remove the error class if we're displaying the error for another
     * reason.
     */
    if (!duplicatedLayerName.is(":visible"))
      layerNameCtrl.removeClass("error")

    $("#invalid-layer-name-hint").hide();
    check_form();
  });

  /* Have a guess at the layer name */
  vcsURLInput.focusout(function (){
    /* If we a layer name specified don't overwrite it or if there isn't a
     * url typed in yet return
     */
    if (layerNameInput.val() || !$(this).val())
      return;

    if ($(this).val().search("/")){
      var urlPts = $(this).val().split("/");
      var suggestion = urlPts[urlPts.length-1].replace(".git","");
      layerNameInput.val(suggestion);
    }
  });

}
