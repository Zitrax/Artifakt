$(function () {

    function addCustomer() {
        dialog.dialog("close");
        var name = $("#name").val();
        $.post('', {name: name})
            .done(function () {
                var $new_customer = $('<tr><td>' + name + '</td></tr>');
                $('#customers tr:last').after($new_customer);
                $('#name').val('');
            })
            .fail(function () {
                alert("Failed to add customer");
            });
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