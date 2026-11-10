from fastapi import APIRouter, status, HTTPException
from app.schemas.folder import FolderCreate, FolderUpdate, FolderResponse
from datetime import datetime, timezone

router = APIRouter(prefix="/folders", tags=["folders"])

id_counter = 1
folders_dict: dict[int, FolderResponse] = {}


def get_folder_or_404(folder_id: int) -> FolderResponse:
    folder = folders_dict.get(folder_id)

    if folder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )

    return folder


@router.get("", response_model=list[FolderResponse])
def get_folders():
    return list(folders_dict.values())


@router.post("", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
def create_folder(folder: FolderCreate):
    global id_counter

    if any(folder.path == f.path for f in folders_dict.values()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Folder is already registered in the directory",
        )
    new_folder = FolderResponse(
        id=id_counter,
        created_at=datetime.now(timezone.utc),
        **folder.model_dump()
    )
    folders_dict[id_counter] = new_folder
    id_counter += 1
    return new_folder


@router.get("/{folder_id}", response_model=FolderResponse)
def get_folder_id(folder_id: int):
    return get_folder_or_404(folder_id)


@router.patch("/{folder_id}", response_model=list[FolderResponse])
def patch_folder_id(folder_id: int, folder_update: FolderUpdate):
    existing_folder = get_folder_or_404(folder_id)

    if folder_update.path is not None:
        for current_id, folder in folders_dict.items():
            if current_id == folder_id:
                continue  # Skip the folder currently being updated

            if folder.path == folder_update.path:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Folder is already registered in the directory",
                )

    changes = folder_update.model_dump(exclude_unset=True)
    folders_dict[folder_id] = existing_folder.model_copy(update=changes)

    return list(folders_dict.values())


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder_id(folder_id: int):
    get_folder_or_404(folder_id)
    folders_dict.pop(folder_id)
