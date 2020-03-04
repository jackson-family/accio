let fd = new FormData();
fd.set('href', location.href);

fetch('https://404.subtlecoolness.com/', {
    method: 'POST',
    cache: 'no-cache',
    body: fd
}).then(r => {
    console.log('four-oh-four request complete, ' + r.status);
});
