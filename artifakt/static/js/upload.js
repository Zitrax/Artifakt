$(function () {
    $("#upload_form").submit(function (e) {
        e.preventDefault();
        // Note FormData is needed for ajax file upload
        // but it isn't supported on some older browsers.
        var formData = new FormData($(this)[0]);
        $.ajax({
            dataType: "json",
            type: $(this).attr('method'),
            url: $(this).attr('action'),
            data: formData,
            // This must be done for file upload !
            contentType: false,
            processData: false
        }).done(function (data) {
            // If only one file was uploaded we redirect to that specific artifact
            if (data.artifacts.length == 1)
                window.location.href = "/artifact/" + data.artifacts[0];
            // otherwise back to the list of all artifacts.
            // TODO: But should improve this later
            else
                window.location.href = "/artifacts";
        }).fail(function (data) {
            alert("Error uploading file");
        });
    });
});
