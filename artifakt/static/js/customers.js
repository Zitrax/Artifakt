$(function () {

    function addCustomer() {
        dialog.dialog("close");
        var name = $("#name").val();
        $.post('', {name: name})
            .done(function () {
                var $new_customer = $('<tr style="display: none;"><td>' + name + '</td></tr>');
                $('#customers').find('tr:first').after($new_customer);
                $new_customer.fadeIn(400);
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
        open: function () {
            $("#dialog-form").off('keypress').on('keypress', function (e) {
                if (e.keyCode == $.ui.keyCode.ENTER) {
                    $(this).parent().find('.ui-dialog-buttonpane button:first').click();
                    e.preventDefault();
                }
            });
        },
        close: function () {
        }
    });

    $('#add_customer').click(function () {
        dialog.dialog("open");
    });

});