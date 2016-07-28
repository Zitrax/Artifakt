$(function () {
    $("form.view_content").submit(function (e) {
        var fsize = parseInt($('#file_size').text());
        if (fsize > 2000000 && !$(this).hasClass('confirmed')) {
            e.preventDefault();
            if (confirm("This file is rather large, are you sure you want to display it ?")) {
                $(this).addClass('confirmed');
                $(this).submit();
            }
        }
    });
    $("#delete").submit(function (e) {
        if (!$(this).hasClass('confirmed')) {
            e.preventDefault();
            if (confirm("Delete " + $('#filename').text() + " ?")) {
                $(this).addClass('confirmed');
                $(this).submit();
            }
        }
    });

    function add_delivery() {
        delivery_dialog.dialog("close");
        var sha1 = window.location.pathname.split('/').pop();
        $.ajax({
            url: window.location.pathname + '/delivery',
            data: JSON.stringify({
                'artifakt_sha1': sha1,
                'comment': $('#delivery_comment').val(),
                'target_id': $('#customer').val(),
                'time': $('#delivery_time').val()
            }),
            type: "POST",
            contentType: "application/json; charset=utf-8",
            dataType: "json"
        }).done(function (data) {
            $('#delivery_comment').val('');
            $('#customer').val('');
            $('#delivery_time').val(new Date().toDateInputValue());

            $('#deliveries tr:last').after($('<tr>' +
                '<td>' + new Date(data.time).toLocaleString() + '</td>' +
                '<td>' + data.to.name + '</td>' +
                '<td>' + data.comment + '</td>' +
                '<td>' + data.by.username + '</td></tr>'))

        }).fail(function () {
            alert('fail');
        });

    }

    var delivery_dialog = $("#delivery-dialog").dialog({
        autoOpen: false,
        modal: true,
        buttons: {
            "Add delivery": add_delivery,
            Cancel: function () {
                delivery_dialog.dialog("close");
            }
        },
        close: function () {
        }
    });

    $('#add_delivery').click(function (e) {
        delivery_dialog.dialog("open");
    });

    $.getJSON('/customers.json', function (data) {
        $.each(data.customers, function (key, value) {
            $('#customer')
                .append($("<option></option>")
                    .attr("value", value.id)
                    .text(value.name));
        })
    });

    Date.prototype.toDateInputValue = (function () {
        var local = new Date(this);
        local.setMinutes(this.getMinutes() - this.getTimezoneOffset());
        return local.toJSON().slice(0, 10);
    });

    $('#delivery_time').val(new Date().toDateInputValue());

    function add_comment(comment, parent_id, target, input) {
        var sha1 = window.location.pathname.split('/').pop();
        $.ajax({
            url: window.location.pathname + '/comment',
            data: JSON.stringify({
                'artifakt_sha1': sha1,
                'comment': comment,
                'parent_id': parent_id
            }),
            type: "POST",
            contentType: "application/json; charset=utf-8",
            dataType: "json"
        }).done(function (data) {
            var $new_comment = $('<li>' +
                '<span class="comment">' + data.comment + '</span>&nbsp;&mdash;&nbsp;' +
                '<span class="comment_by">' + data.user.username + '</span>&nbsp;' +
                '<span class="comment_age" title="">' + data.age + ' ago</span>&nbsp;' +
                '</li>');
            if (target.prop("tagName") == "UL") {
                $new_comment.appendTo(target);
                input.val('');
            } else {
                var ul = target.find('ul');
                if (!ul) {
                    ul = $('<ul>');
                    ul.appendTo(target);
                }
                $new_comment.appendTo(ul);
                input.parent().remove();
            }
        }).fail(function () {
            alert('fail');
        });
    }

    $('#new_comment').keypress(function (e) {
        if (e.which == 13) {
            add_comment($(this).val(), null, $('#comments'), $(this));
        }
    });

    $("span.comment_reply a").click(function (e) {
        // First remove any existing reply box
        $('.reply_list').remove();
        // Add new
        var $reply = $('<ul class="reply_list"><li>' +
            '<input data-reply-id="' + $(this).data("comment-id") + '" class="input-sm" type="text" placeholder="Reply">' +
            '</li></ul>');
        var $target = $(this).parent().parent();
        $reply.appendTo($target);
        $reply.find('input').focus().keypress(function (e) {
            if (e.which == 13) {
                add_comment($(this).val(), $(this).data("reply-id"), $target, $(this));
            }
        });
    });
});

