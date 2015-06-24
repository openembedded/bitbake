'use strict';

function basePageInit(ctx) {

  var newBuildButton = $("#new-build-button");
  /* Hide the button if we're on the project,newproject or importlyaer page
   * or if there are no projects yet defined
   */
  if (ctx.numProjects === 0 || ctx.currentUrl.search('newproject|project/\\d$|importlayer$') > 0) {
    newBuildButton.hide();
    return;
  }

  var selectedProject = libtoaster.ctx;
  var selectedTarget;

  /* Hide the change project icon when there is only one project */
  if (ctx.numProjects === 1) {
    $('#project .icon-pencil').hide();
  }

  newBuildButton.show().removeAttr("disabled");


  var newBuildProjectInput = $("#new-build-button #project-name-input");
  var newBuildTargetBuildBtn = $("#new-build-button #build-button");
  var newBuildTargetInput = $("#new-build-button #build-target-input");
  var newBuildProjectSaveBtn = $("#new-build-button #save-project-button");


  _checkProjectBuildable();
  _setupNewBuildButton();


  function _checkProjectBuildable() {
    if (selectedProject.projectId === undefined) {
      return;
    }

    libtoaster.getProjectInfo(selectedProject.projectPageUrl,
      function (data) {
        if (data.machine === null || data.machine.name === undefined || data.layers.length === 0) {
          /* we can't build anything with out a machine and some layers */
          $("#new-build-button #targets-form").hide();
          $("#new-build-button .alert").show();
        } else {
          $("#new-build-button #targets-form").show();
          $("#new-build-button .alert").hide();

          /* we can build this project; enable input fields */
          newBuildTargetInput.prop("disabled", false);
          newBuildTargetBuildBtn.prop("disabled", false);

          libtoaster.makeTypeahead(newBuildTargetInput, selectedProject.projectTargetsUrl, { format: "json" }, function (item) {
            /* successfully selected a target */
            selectedProject.projectPageUrl = item.projectPageUrl;
            selectedProject.projectName = item.name;
            selectedProject.projectId = item.id;
            selectedProject.projectBuildsUrl = item.projectBuildsUrl;


          });

        }
      }, null);
  }

  function _setupNewBuildButton() {
    /* Setup New build button */

    /* If we don't have a current project then present the set project
     * form.
     */
    if (selectedProject.projectId === undefined) {
      $('#change-project-form').show();
      $('#project .icon-pencil').hide();
    }


    libtoaster.makeTypeahead(newBuildProjectInput, selectedProject.projectsUrl, { format : "json" }, function (item) {
      /* successfully selected a project */
      newBuildProjectSaveBtn.removeAttr("disabled");
      selectedProject = item;
    });

    /* Any typing in the input apart from enter key is going to invalidate
     * the value that has been set by selecting a suggestion from the typeahead
     */
    newBuildProjectInput.on('input', function (event) {
      if (event.keyCode === 13) {
        return;
      }
      newBuildProjectSaveBtn.attr("disabled", "disabled");
    });

    newBuildTargetInput.on('input', function () {
      if ($(this).val().length === 0) {
        newBuildTargetBuildBtn.attr("disabled", "disabled");
      } else {
        newBuildTargetBuildBtn.removeAttr("disabled");
      }
    });

    newBuildTargetBuildBtn.click(function () {
      if (!newBuildTargetInput.val()) {
        return;
      }

      if (!selectedTarget) {
        selectedTarget = { name: newBuildTargetInput.val() };
      }
      /* fire and forget */
      libtoaster.startABuild(selectedProject.projectBuildsUrl, selectedProject.projectId, selectedTarget.name, null, null);
      window.location.replace(selectedProject.projectPageUrl);
    });

    newBuildProjectSaveBtn.click(function () {
      selectedProject.projectId = selectedProject.pk;
      /* Update the typeahead project_id paramater */
      _checkProjectBuildable();

      /* we set the effective context of the page to the currently selected project */
      /* TBD: do we override even if we already have a context project ?? */
      /* TODO: replace global library context with references to the "selected" project */

      /* we can create a target typeahead only after we have a project selected */
      newBuildTargetInput.prop("disabled", false);
      newBuildTargetBuildBtn.prop("disabled", false);

      libtoaster.makeTypeahead(newBuildTargetInput, selectedProject.projectTargetsUrl, { format: "json" }, function (item) {
        /* successfully selected a target */
        selectedTarget = item;
      });

      newBuildTargetInput.val("");

      /* set up new form aspect */
      $("#new-build-button #project a").text(selectedProject.name).attr('href', selectedProject.projectPageUrl);
      $("#new-build-button .alert a").attr('href', selectedProject.projectPageUrl);
      $("#project .icon-pencil").show();

      $("#change-project-form").slideUp({ 'complete' : function () {
          $("#new-build-button #project").show();
      }});
    });

    $('#new-build-button #project .icon-pencil').click(function () {
      newBuildProjectSaveBtn.attr("disabled", "disabled");
      newBuildProjectInput.val($("#new-build-button #project a").text());
      $("#cancel-change-project").show();
      $(this).parent().hide();
      $("#change-project-form").slideDown();
    });

    $("#new-build-button #cancel-change-project").click(function () {
      $("#change-project-form").hide(function () {
        $('#new-build-button #project').show();
      });

      newBuildProjectInput.val("");
      newBuildProjectSaveBtn.attr("disabled", "disabled");
    });

    /* Keep the dropdown open even unless we click outside the dropdown area */
    $(".new-build").click (function (event) {
      event.stopPropagation();
    });
  };

}
