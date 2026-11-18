"""Atomic JSON save slots and automatically flushed project settings."""
from collections.abc import MutableMapping
from copy import deepcopy
from pathlib import Path
import json
import os
import re
import sys
import tempfile


class SaveError(ValueError):pass


def user_data_dir(app_id):
    if not isinstance(app_id,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+',app_id) or app_id in ('.','..'):
        raise ValueError('app_id must be a simple nonempty identifier')
    if sys.platform=='win32':base=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))
    elif sys.platform=='darwin':base=Path.home()/'Library/Application Support'
    else:base=Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))
    return base/'doku2d'/app_id


class SaveStore:
    def __init__(self,root=None,*,app_id='doku2d-game'):
        self._root=Path(root).resolve() if root is not None else user_data_dir(app_id)
    @property
    def root(self):return self._root
    def _path(self,slot):
        if not isinstance(slot,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',slot):
            raise ValueError('Save slot must use letters, digits, underscores or hyphens')
        return self.root/(slot+'.json')
    def save(self,slot,data):
        path=self._path(slot)
        try:payload=json.dumps(data,ensure_ascii=False,allow_nan=False,indent=2)+'\n'
        except (TypeError,ValueError) as error:raise SaveError(f'Save data must contain JSON values: {error}') from error
        self.root.mkdir(parents=True,exist_ok=True)
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',newline='\n',dir=self.root,prefix='.'+slot+'-',suffix='.tmp',delete=False) as stream:
                temporary=Path(stream.name);stream.write(payload);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,path)
        finally:
            if temporary is not None:temporary.unlink(missing_ok=True)
        return path
    def load(self,slot,default=None):
        path=self._path(slot)
        if not path.exists():return deepcopy(default)
        try:
            return json.loads(path.read_text(encoding='utf-8-sig'),parse_constant=lambda token:(_ for _ in ()).throw(ValueError(token)))
        except (ValueError,UnicodeError) as error:raise SaveError(f'Invalid JSON save: {path.name}') from error
    def exists(self,slot):return self._path(slot).is_file()
    def delete(self,slot):
        path=self._path(slot);existed=path.exists();path.unlink(missing_ok=True);return existed
    def list_slots(self):return tuple(sorted(path.stem for path in self.root.glob('*.json') if re.fullmatch(r'[A-Za-z0-9_-]{1,80}',path.stem)))


class Settings(MutableMapping):
    def __init__(self,store,defaults=None):
        self.store=store
        loaded=store.load('settings',{})
        if not isinstance(loaded,dict):raise SaveError('Settings file must contain a JSON object')
        self._data=deepcopy(defaults or {});self._data.update(loaded);self._original=deepcopy(self._data)
    def __getitem__(self,key):return self._data[key]
    def __setitem__(self,key,value):
        if not isinstance(key,str):raise TypeError('Setting names must be strings')
        self._data[key]=value
    def __delitem__(self,key):del self._data[key]
    def __iter__(self):return iter(self._data)
    def __len__(self):return len(self._data)
    def save(self):
        result=self.store.save('settings',self._data);self._original=deepcopy(self._data);return result
    def flush(self):
        if self._data!=self._original:self.save()


__all__=['SaveStore','Settings','SaveError']
