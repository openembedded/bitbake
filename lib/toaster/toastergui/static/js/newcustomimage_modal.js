"use strict";

/* Used for the newcustomimage_modal actions */
function newCustomImageModalInit(){

  var newCustomImgBtn = $("#create-new-custom-image-btn");
  var imgCustomModal = $("#new-custom-image-modal");

  newCustomImgBtn.click(function(e){
    e.preventDefault();

    var name = imgCustomModal.find('input').val();
    var baseRecipeId = imgCustomModal.data('recipe');

    if (name.length > 0) {
      imgCustomModal.modal('hide');
      libtoaster.createCustomRecipe(name, baseRecipeId, function(ret) {
        if (ret.error !== "ok") {
          console.warn(ret.error);
        } else {
          window.location.replace(ret.url + '?notify=new');
        }
      });
    } else {
      console.warn("TODO No name supplied");
    }
  });
}
