

function basePageInit (ctx) {

  var newBuildButton = $("#new-build-button");
  /* Hide the button if we're on the project,newproject or importlyaer page
   * or if there are no projects yet defined
   */
  if (ctx.numProjects == 0 || ctx.currentUrl.search('newproject|project/\\d/$|importlayer/$') > 0){
      newBuildButton.hide();
      return;
  }

  /* Hide the change project icon when there is only one project */
  if (ctx.numProjects == 1){
     $('#project .icon-pencil').hide(); 
  }

  newBuildButton.show().removeAttr("disabled");

  _checkProjectBuildable()
  _setupNewBuildButton();


  function _checkProjectBuildable(){
    if (ctx.projectId == undefined)
      return;

    libtoaster.getProjectInfo(ctx.projectInfoUrl, ctx.projectId,
      function(data){
        if (data.machine.name == undefined || data.layers.length == 0) {
          /* we can't build anything with out a machine and some layers */
          $("#new-build-button #targets-form").hide();
          $("#new-build-button .alert").show();
        } else {
          $("#new-build-button #targets-form").show();
          $("#new-build-button .alert").hide();
        }
    }, null);
  }

  function _setupNewBuildButton() {
    /* Setup New build button */
    var newBuildProjectInput = $("#new-build-button #project-name-input");
    var newBuildTargetBuildBtn = $("#new-build-button #build-button");
    var newBuildTargetInput = $("#new-build-button #build-target-input");
    var newBuildProjectSaveBtn = $("#new-build-button #save-project-button");
    var selectedTarget;
    var selectedProject;

    /* If we don't have a current project then present the set project
     * form.
     */
    if (ctx.projectId == undefined) {
      $('#change-project-form').show();
      $('#project .icon-pencil').hide();
    }

    libtoaster.makeTypeahead(newBuildTargetInput, ctx.xhrDataTypeaheadUrl, { type : "targets", project_id: ctx.projectId }, function(item){
        /* successfully selected a target */
        selectedTarget = item;
    });


    libtoaster.makeTypeahead(newBuildProjectInput, ctx.xhrDataTypeaheadUrl, { type : "projects" }, function(item){
        /* successfully selected a project */
        newBuildProjectSaveBtn.removeAttr("disabled");
        selectedProject = item;
    });

    /* Any typing in the input apart from enter key is going to invalidate
     * the value that has been set by selecting a suggestion from the typeahead
     */
    newBuildProjectInput.on('input', function(event) {
        if (event.keyCode == 13)
          return;
        newBuildProjectSaveBtn.attr("disabled", "disabled");
    });

    newBuildTargetInput.on('input', function() {
      if ($(this).val().length == 0)
        newBuildTargetBuildBtn.attr("disabled", "disabled");
      else
        newBuildTargetBuildBtn.removeAttr("disabled");
    });

    newBuildTargetBuildBtn.click(function() {
      if (!newBuildTargetInput.val())
        return;

      if (!selectedTarget)
        selectedTarget = { name: newBuildTargetInput.val() };
      /* fire and forget */
      libtoaster.startABuild(ctx.projectBuildUrl, ctx.projectId, selectedTarget.name, null, null);
      window.location.replace(ctx.projectPageUrl+ctx.projectId);
    });

    newBuildProjectSaveBtn.click(function() {
      ctx.projectId = selectedProject.id
      /* Update the typeahead project_id paramater */
      _checkProjectBuildable();
      newBuildTargetInput.data('typeahead').options.xhrParams.project_id = ctx.projectId;
      newBuildTargetInput.val("");

      $("#new-build-button #project a").text(selectedProject.name).attr('href', ctx.projectPageUrl+ctx.projectId);
      $("#new-build-button .alert a").attr('href', ctx.projectPageUrl+ctx.projectId);


      $("#change-project-form").slideUp({ 'complete' : function() {
          $("#new-build-button #project").show();
      }});
    });

    $('#new-build-button #project .icon-pencil').click(function() {
      newBuildProjectSaveBtn.attr("disabled", "disabled");
      newBuildProjectInput.val($("#new-build-button #project a").text());
      $(this).parent().hide();
      $("#change-project-form").slideDown();
    });

    $("#new-build-button #cancel-change-project").click(function() {
      $("#change-project-form").hide(function(){
        $('#new-build-button #project').show();
      });

      newBuildProjectInput.val("");
      newBuildProjectSaveBtn.attr("disabled", "disabled");
    });

    /* Keep the dropdown open even unless we click outside the dropdown area */
    $(".new-build").click (function(event) {
      event.stopPropagation();
    });
  };

}
