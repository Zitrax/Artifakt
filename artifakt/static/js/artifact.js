$(function () {
    $("form.view_content").submit(function (e) {
        var fsize = parseInt($('#file_size').text());
        if(fsize > 2000000 &&
            !$(this).hasClass('confirmed')) {
            e.preventDefault();
            if (confirm("This file is rather large, are you sure you want to display it ?")) {
                $(this).addClass('confirmed');
                $(this).submit();
            }
        }
    });
});
