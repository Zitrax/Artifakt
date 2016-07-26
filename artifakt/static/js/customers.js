$(function () {

    function addCustomer() {
        alert($("#name").val());
    }

    var dialog = $("#dialog-form").dialog({
        autoOpen: false,
        modal: true,
        buttons: {
            "Add customer": addCustomer,
            Cancel: function () {
                dialog.dialog("close");
            }
        },
        close: function () {
        }
    });

    $('#add_customer').click(function () {
        dialog.dialog("open");
    });

});