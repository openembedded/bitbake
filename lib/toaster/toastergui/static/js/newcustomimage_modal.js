"use strict";

/* Used for the newcustomimage_modal actions */
function newCustomImageModalInit(){

  var newCustomImgBtn = $("#create-new-custom-image-btn");
  var imgCustomModal = $("#new-custom-image-modal");
  var invalidNameHelp = $("#invalid-name-help");
  var nameInput = imgCustomModal.find('input');

  var invalidMsg = "Image names cannot contain spaces or capital letters. The only allowed special character is dash (-).";

  newCustomImgBtn.click(function(e){
    e.preventDefault();

    var baseRecipeId = imgCustomModal.data('recipe');

    if (nameInput.val().length > 0) {
      libtoaster.createCustomRecipe(nameInput.val(), baseRecipeId,
      function(ret) {
        if (ret.error !== "ok") {
          console.warn(ret.error);
          if (ret.error === "invalid-name") {
            showError(invalidMsg);
          } else if (ret.error === "already-exists") {
            showError("An image with this name already exists. Image names must be unique.");
          }
        } else {
          imgCustomModal.modal('hide');
          window.location.replace(ret.url + '?notify=new');
        }
      });
    }
  });

  function showError(text){
    invalidNameHelp.text(text);
    invalidNameHelp.show();
    nameInput.parent().addClass('error');
  }

  nameInput.on('keyup', function(){
    if (nameInput.val().length === 0){
      newCustomImgBtn.prop("disabled", true);
      return
    }

    if (nameInput.val().search(/[^a-z|0-9|-]/) != -1){
      showError(invalidMsg);
      newCustomImgBtn.prop("disabled", true);
      nameInput.parent().addClass('error');
    } else {
      invalidNameHelp.hide();
      newCustomImgBtn.prop("disabled", false);
      nameInput.parent().removeClass('error');
    }
  });
}
