import hashlib
import json
from uuid import UUID
from fastapi import HTTPException
from .attachments import storage_guard,attachment_path
from .db import connect
from .records import dumps


def _cleanup_files_locked(settings,strict=False):
    with connect(settings) as con:
        con.execute('BEGIN IMMEDIATE')
        for row in con.execute('SELECT id FROM deletion_file_cleanup').fetchall():
            aid=row['id']
            try:
                if not con.execute('SELECT 1 FROM attachments WHERE id=?',(aid,)).fetchone():
                    attachment_path(settings,str(UUID(aid))).unlink(missing_ok=True)
                con.execute('DELETE FROM deletion_file_cleanup WHERE id=?',(aid,))
            except OSError:
                if strict:raise


def cleanup_deleted_files(settings):
    with storage_guard(settings):_cleanup_files_locked(settings)


def delete_idea(settings,owner,id,mutation):
    if mutation.payload:
        raise HTTPException(422,"删除操作不接受正文")
    fingerprint=hashlib.sha256(dumps(['delete',id,mutation.model_dump(mode='json')]).encode()).hexdigest()
    ack={'mutation_id':str(mutation.mutation_id),'accepted_version':1}
    with storage_guard(settings):
        with connect(settings) as con:
            con.execute('BEGIN IMMEDIATE')
            prior=con.execute('SELECT * FROM mutations WHERE owner=? AND id=?',(owner,str(mutation.mutation_id))).fetchone()
            if prior and prior['fingerprint']!=fingerprint:
                raise HTTPException(409,"重试标识已用于不同请求")
            deleted=con.execute('SELECT * FROM deleted_ideas WHERE id=?',(id,)).fetchone()
            if deleted:
                if deleted['owner']!=owner:raise HTTPException(404,"未找到记录")
                payload=json.loads(deleted['payload'])
            else:
                if not con.execute("SELECT 1 FROM entities WHERE owner=? AND id=? AND kind='record'",(owner,id)).fetchone():
                    raise HTTPException(404,"未找到记录")
                aids={row[0] for row in con.execute('SELECT attachment_id FROM attachment_refs WHERE owner=? AND idea_id=?',(owner,id))}
                for row in con.execute("SELECT payload FROM events WHERE owner=? AND entity_id=? AND kind='record'",(owner,id)):
                    aids.update(image['id'] for image in json.loads(row[0]).get('attachments',[]))
                aids=sorted(aids)
                payload={'id':id,'attachment_ids':aids}
                encoded=dumps(payload)
                con.execute('INSERT INTO deleted_ideas VALUES(?,?,?)',(id,owner,encoded))
                con.execute('DELETE FROM attachment_refs WHERE owner=? AND idea_id=?',(owner,id))
                con.execute('DELETE FROM entities WHERE owner=? AND id=?',(owner,id))
                con.execute("DELETE FROM events WHERE owner=? AND entity_id=? AND kind<>'attachment'",(owner,id))
                for aid in aids:
                    if not con.execute('SELECT 1 FROM attachment_refs WHERE attachment_id=?',(aid,)).fetchone():
                        con.execute('DELETE FROM attachments WHERE owner=? AND id=?',(owner,aid))
                        con.execute("DELETE FROM events WHERE owner=? AND entity_id=? AND kind='attachment'",(owner,aid))
                        con.execute('INSERT OR IGNORE INTO deletion_file_cleanup VALUES(?)',(aid,))
                con.execute("INSERT INTO events(owner,kind,entity_id,payload) VALUES(?,'delete',?,?)",(owner,id,encoded))
            con.execute('INSERT OR IGNORE INTO mutations VALUES(?,?,?,?)',(owner,str(mutation.mutation_id),fingerprint,dumps(ack)))
        # Persisted cleanup survives a lost response and clients consuming the deletion event.
        _cleanup_files_locked(settings,strict=True)
    return ack
