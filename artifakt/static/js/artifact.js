$(function () {
    $.fn.editable.defaults.mode = 'inline';
    $('#editable_filename').editable({
        type: 'text',
        url: window.location.pathname + '/edit',
        pk: 1,  // Not used - but seem to be needed to make the request
        name: 'name',
        tpl: "<input type='text' style='width: 400px'>"
    });
    $('.editable_comment').on('init', function (e, edt) {
        // The url setting can't use this directly in editable since $(this)
        // refers to the global window object. Neither can a function simply be used
        // since it replaces the ajax request.
        // A workaround is to use init like this.
        edt.options.url = window.location.pathname + '/comment_edit/' + $(this).data('id');
    }).editable({
        type: 'text',
        pk: 1,  // Not used - but seem to be needed to make the request
        name: 'comment',
        tpl: "<input type='text' style='width: 400px'>",
        toggle: "manual"
    });
    $('.edit_comment').click(function (e) {
        e.stopPropagation();
        $(e.target).siblings('.editable_comment').editable('toggle');
    });

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

            var $new_row = $('<tr style="display: none;">' +
                '<td>' + new Date(data.time).toLocaleDateString() + '</td>' +
                '<td>' + data.to.name + '</td>' +
                '<td>' + data.comment + '</td>' +
                '<td>' + data.by.username + '</td>' +
                '<td><span data-id="' + data.id + '" data-name="' + data.to.name + '" data-time="' +
                new Date(data.time).toLocaleDateString() + '" class="delete_delivery glyphicon glyphicon-trash"' +
                ' aria-hidden="true"></span></td>' +
                '</tr>'
            );
            $('#deliveries').show().find('tr:first').after($new_row);
            $new_row.fadeIn(400);


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
        open: function () {
            $("#delivery-dialog").off('keypress').on('keypress', function (e) {
                if (e.keyCode == $.ui.keyCode.ENTER) {
                    $(this).parent().find('.ui-dialog-buttonpane button:first').click();
                    e.preventDefault();
                }
            });
        }
    });

    $('#add_delivery').click(function () {
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

    $(document).on('click', 'span.delete_comment', function () {
        $('#comment_delete_text').text($(this).siblings('.comment').text());
        var span_delete = $(this);
        $("#delete_comment_confirm").dialog({
            width: 400,
            modal: true,
            buttons: {
                "Delete comment": function () {
                    $(this).dialog("close");
                    $.post(window.location.pathname + '/comment_delete/' + span_delete.data('id'), function () {
                        var li = span_delete.closest('li');
                        if (li.has("ul").length) {
                            li.find('> span.comment').fadeOut(function () {
                                $(this).text('<DELETED>').fadeIn();
                            });
                        }
                        else {
                            li.fadeOut(400, function () {
                                $(this).remove();
                            });
                        }
                    });
                },
                Cancel: function () {
                    $(this).dialog("close");
                }
            }
        });
    });

    $(document).on('click', 'span.delete_delivery', function () {
        $('#delivery_delete_name').text($(this).data('name'));
        $('#delivery_delete_time').text(new Date($(this).data('time') + ' UTC').toLocaleDateString());
        var td_delete = $(this);
        $("#delete_delivery_confirm").dialog({
            width: 400,
            modal: true,
            buttons: {
                "Delete delivery": function () {
                    $(this).dialog("close");
                    $.post(window.location.pathname + '/delivery_delete/' + td_delete.data('id'), function () {
                        td_delete.closest('tr').fadeOut(400, function () {
                            $(this).remove();
                        });
                    });
                },
                Cancel: function () {
                    $(this).dialog("close");
                }
            }
        });

    });

    function add_comment(comment, parent_id, target, input) {
        if (comment.length == 0)
            return;
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
                var ul = target.find('ul:not(.reply_list)');
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

    $('#new_comment_button').click(function () {
        var $new_comment = $('#new_comment');
        add_comment($new_comment.val(), null, $('#comments'), $new_comment);
    });

    $("span.comment_reply").click(function () {
        // First remove any existing reply box
        $('.reply_list').remove();
        // Add new
        var $reply = $('<ul class="reply_list"><li>' +
            '<input data-reply-id="' + $(this).data("comment-id") + '" class="input-sm" type="text" placeholder="Reply">' +
            '&nbsp;<button class="btn btn-sm btn-default" type="submit">Add reply</button>' +
            '</li></ul>');
        var $target = $(this).parent();
        $reply.appendTo($target);
        $reply.find('input').focus().keypress(function (e) {
            if (e.which == 13) {
                add_comment($(this).val(), $(this).data("reply-id"), $target, $(this));
            }
        });
        $reply.find('button').click(function (e) {
            var $reply_input = $reply.find('input');
            add_comment($reply_input.val(), $reply_input.data("reply-id"), $target, $reply_input);
        });
    });


    $('span.comment').each(linkify);
});

