"use strict"

function machinesPageInit (ctx) {


  function setLayerInCurrentPrj(addLayerBtn, depsList){
    var alertMsg = $("#alert-msg");

    $(".select-or-add").each(function(){
      /* If we have added a layer it may also enable other machines so search
       * for other machines that have that layer and enable them */
      var selectMachineBtn = $(this).children(".select-machine-btn");
      var otherAddLayerBtns = $(this).children(".add-layer");

      if (addLayerBtn.data('layer-version-id') ==  selectMachineBtn.data('layer-version-id')) {
        otherAddLayerBtns.fadeOut(function(){
          selectMachineBtn.fadeIn();
        });
      }
    });

    /* Reset alert message */
    alertMsg.text("");

    /* If we have added layer dependencies */
    if (depsList) {
      alertMsg.append("You have added <strong>"+(depsList.length+1)+"</strong> layers to <a id=\"project-affected-name\"></a>: <span id=\"layer-affected-name\"></span> and its dependencies ");

        /* Build the layer deps list */
        depsList.map(function(layer, i){
          var link = $("<a></a>");

          link.attr("href", layer.layerdetailurl);
          link.text(layer.name);
          link.tooltip({title: layer.tooltip});

          if (i != 0)
            alertMsg.append(", ");

          alertMsg.append(link);
        });
    } else {
      alertMsg.append("You have added <strong>1</strong> layer to <a id=\"project-affected-name\"></a>: <strong id=\"layer-affected-name\"></strong>");
    }

    var layerName = addLayerBtn.data('layer-name');
    alertMsg.children("#layer-affected-name").text(layerName);
    alertMsg.children("#project-affected-name").text(ctx.projectName).attr('href', ctx.projectPageUrl);

    $("#alert-area").show();
  }

  $("#dismiss-alert").click(function(){ $(this).parent().hide() });

  /* Add or remove this layer from the project */
  $(".add-layer").click(function() {
      var btn = $(this);
      /* If adding get the deps for this layer */
      var layer = {
        id : $(this).data('layer-version-id'),
        name : $(this).data('layer-name'),
      };

      libtoaster.getLayerDepsForProject(ctx.xhrDataTypeaheadUrl, ctx.projectId, layer.id, function (data) {
        /* got result for dependencies */
        if (data.list.length == 0){
          var editData = { layerAdd : layer.id };
          libtoaster.editProject(ctx.xhrEditProjectUrl, ctx.projectId, editData,
            function() {
              setLayerInCurrentPrj(btn);
          });
          return;
        } else {
          /* The add deps will include this layer so no need to add it
           * separately.
           */
          show_layer_deps_modal(ctx.projectId, layer, data.list, null, null, true, function () {
            /* Success add deps and layer */
            setLayerInCurrentPrj(btn, data.list);
          });
        }
      }, null);
  });

  $(".select-machine-btn").click(function(){
    var data =  { machineName : $(this).data('machine-name') };
    libtoaster.editProject(ctx.xhrEditProjectUrl, ctx.projectId, data,
      function (){
        window.location.replace(ctx.projectPageUrl+"#/machineselected");
    }, null);
  });

  $("#show-all-btn").click(function(){
    $("#search").val("")
    $("#searchform").submit();
  });
}
