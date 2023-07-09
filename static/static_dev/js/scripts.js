$(document).ready(function (){

    $("#modal_close_btn").on("click", function (){
        modal_el = $(this).closest(".modal");
        modal_el.modal("hide");
    })
})