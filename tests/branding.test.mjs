import test from 'node:test';
import assert from 'node:assert/strict';
import {paletteFromPixels,readableInk,luminance,validColor} from '../public/branding.js';

test('ignores a white background and transparent pixels when suggesting brand colors',()=>{
    const pixels=[];
    for(let i=0;i<100;i++)pixels.push(255,255,255,255);
    for(let i=0;i<30;i++)pixels.push(22,148,72,255);
    for(let i=0;i<10;i++)pixels.push(235,128,35,255);
    for(let i=0;i<200;i++)pixels.push(255,0,0,0);
    assert.deepEqual(paletteFromPixels(pixels),{primary:'#169448',secondary:'#eb8023'});
});
test('provides usable colors for monochrome and single-color logos',()=>{
    assert.deepEqual(paletteFromPixels([0,0,0,255,255,255,255,255]),{primary:'#444444',secondary:'#888888'});
    const palette=paletteFromPixels([22,148,72,255]);
    assert.match(palette.secondary,/^#[a-f0-9]{6}$/);assert.notEqual(palette.primary,palette.secondary);
});
test('selects legible text on bright and dark logo colors',()=>{
    for(const color of ['#ffff00','#000080','#169448','#eb8023','#ffffff','#000000']){
        const foreground=luminance(readableInk(color)),background=luminance(color);
        assert.ok((Math.max(foreground,background)+0.05)/(Math.min(foreground,background)+0.05)>=4.5,color);
    }
    assert.equal(validColor('url(https://example.com)'),'#f13b30');
});
